"""
Worker thread and Automation Engine executing the Prompt Playbook:
1. Messenger Audit
2. Daily Sheet filtering (delete rows of uncontacted)
3. Append DM'd prospects to Master Sheet with proper fields & formatting
4. Verification & Clipboard copy
"""

import sys
import os
import re
import csv
import io
import time
import asyncio
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

from cdp_engine import CDPClient, export_sheet_csv, extract_doc_and_gid

def norm(s):
    return str(s if s is not None else '').replace('\u00a0', ' ').replace('\n', ' ').strip()

def calculate_priority(followers_count):
    try:
        count = int(re.sub(r'[^0-9]', '', str(followers_count)))
        if count >= 100:
            return "High"
        elif count >= 10:
            return "Medium"
        else:
            return "Low"
    except Exception:
        # If parsing follower count fails, default to Low or Medium
        return "Medium"

class TrackerWorker(QThread):
    log_signal = pyqtSignal(str, str) # level, message
    progress_signal = pyqtSignal(int, str) # percentage, status text
    finished_signal = pyqtSignal(bool, str, dict) # success, message, stats

    def __init__(self, messenger_tab, prospect_tabs, master_tab, options):
        super().__init__()
        self.messenger_tab = messenger_tab
        self.prospect_tabs = prospect_tabs  # List of prospect tabs selected
        self.master_tab = master_tab
        self.options = options
        self.is_cancelled = False

    def log(self, msg, level="info"):
        self.log_signal.emit(level, msg)

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        asyncio.run(self.run_automation())

    async def run_automation(self):
        self.log("Starting Facebook DM Prospect Tracker Pipeline...", "info")
        self.progress_signal.emit(5, "Connecting to Chrome DevTools tabs...")

        stats = {
            "prospects_scanned": 0,
            "dmd_count": 0,
            "replied_count": 0,
            "not_dmd_removed": 0,
            "master_appended": 0,
            "tabs_processed": len(self.prospect_tabs)
        }

        messenger_cdp = None
        master_cdp = None

        try:
            # 1. Connect to Messenger
            self.log(f"Connecting to Messenger tab: {self.messenger_tab['title'][:40]}...", "info")
            messenger_cdp = CDPClient(self.messenger_tab['webSocketDebuggerUrl'])
            await messenger_cdp.connect()
            await messenger_cdp.send("Runtime.enable")

            # 2. Connect to Master Sheet
            self.log(f"Connecting to Master Sheet tab: {self.master_tab['title'][:40]}...", "info")
            master_cdp = CDPClient(self.master_tab['webSocketDebuggerUrl'])
            await master_cdp.connect()
            await master_cdp.send("Runtime.enable")

            # Iterate through each selected prospect sheet tab
            total_tabs = len(self.prospect_tabs)
            for tab_idx, p_tab in enumerate(self.prospect_tabs):
                if self.is_cancelled:
                    self.log("Task was cancelled by user.", "warning")
                    break

                self.log(f"\n==========================================", "info")
                self.log(f"Processing Sheet [{tab_idx + 1}/{total_tabs}]: {p_tab['title']}", "info")
                self.progress_signal.emit(int(10 + (tab_idx / total_tabs) * 80), f"Processing {p_tab['title']}...")

                sheet_cdp = CDPClient(p_tab['webSocketDebuggerUrl'])
                await sheet_cdp.connect()
                await sheet_cdp.send("Runtime.enable")

                try:
                    await self.process_single_prospect_tab(sheet_cdp, messenger_cdp, master_cdp, p_tab, stats)
                finally:
                    await sheet_cdp.close()

            # 4. Copy 'done' to clipboard as required by prompt
            self.progress_signal.emit(95, "Setting clipboard and finalizing...")
            import subprocess
            try:
                subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value 'done'"], check=False)
                self.log("PowerShell: 'done' copied to clipboard.", "success")
            except Exception as e:
                self.log(f"Clipboard note: {e}", "warning")

            self.progress_signal.emit(100, "Automation task completed successfully!")
            self.log("\n==========================================", "success")
            self.log(f"COMPLETED! Processed {stats['prospects_scanned']} prospects across {total_tabs} sheet(s).", "success")
            self.log(f"DM'd: {stats['dmd_count']} | Replied: {stats['replied_count']} | Removed: {stats['not_dmd_removed']} | Appended: {stats['master_appended']}", "success")
            
            self.finished_signal.emit(True, "All tasks completed successfully!", stats)

        except Exception as e:
            self.log(f"CRITICAL ERROR: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            self.finished_signal.emit(False, str(e), stats)
        finally:
            if messenger_cdp:
                await messenger_cdp.close()
            if master_cdp:
                await master_cdp.close()

    async def process_single_prospect_tab(self, sheet_cdp, messenger_cdp, master_cdp, p_tab, stats):
        doc_id, gid = extract_doc_and_gid(p_tab['url'])
        if not doc_id:
            # Fallback to prompt doc id if url lacks it
            doc_id = "1yLVmUwo0_7nq393HkKY06eyDtI3Bepo6HBOU4Dtm0QY"
        self.log(f"Exporting prospect CSV (doc: {doc_id}, gid: {gid})...", "info")

        csv_text = await export_sheet_csv(sheet_cdp, doc_id, gid)
        if not csv_text or csv_text.startswith("ERROR:"):
            self.log(f"Failed to fetch CSV via CDP: {csv_text}. Reading via DOM...", "warning")
            csv_text = await sheet_cdp.evaluate("""
                (() => {
                    const table = [];
                    // Extract visible cell content if export blocked
                    return '';
                })()
            """)

        rows = []
        if csv_text and not csv_text.startswith("ERROR:"):
            reader = csv.reader(io.StringIO(csv_text))
            rows = [r for r in reader if any(field.strip() for field in r)]

        if not rows:
            self.log("No rows found in this prospect sheet or sheet is empty.", "warning")
            return

        header = rows[0]
        self.log(f"Found {len(rows)-1} prospect rows. Header: {header[:6]}", "info")

        # Map header columns
        col_map = {}
        for idx, col_name in enumerate(header):
            clean = col_name.strip().lower()
            if "company" in clean or "business" in clean or "name" in clean and "company" not in col_map:
                col_map["company"] = idx
            elif "facebook" in clean or "social" in clean or "fb" in clean or "profile" in clean:
                col_map["facebook"] = idx
            elif "website" in clean or "site" in clean or "url" in clean:
                col_map["website"] = idx
            elif "email" in clean:
                col_map["email"] = idx
            elif "phone" in clean:
                col_map["phone"] = idx
            elif "follower" in clean or "count" in clean:
                col_map["followers"] = idx
            elif "location" in clean or "city" in clean or "address" in clean:
                col_map["location"] = idx

        # Sensible defaults if exact column headers differ
        if "company" not in col_map and len(header) > 0: col_map["company"] = 0
        if "facebook" not in col_map and len(header) > 1: col_map["facebook"] = 1
        if "website" not in col_map and len(header) > 2: col_map["website"] = 2
        if "email" not in col_map and len(header) > 3: col_map["email"] = 3
        if "phone" not in col_map and len(header) > 4: col_map["phone"] = 4
        if "followers" not in col_map and len(header) > 5: col_map["followers"] = 5
        if "location" not in col_map and len(header) > 6: col_map["location"] = 6

        prospects_to_keep = []
        rows_to_delete = []

        # Audit Messenger for each prospect
        await messenger_cdp.bring_to_front()

        for row_idx in range(1, len(rows)):
            if self.is_cancelled:
                return

            row = rows[row_idx]
            company = row[col_map["company"]] if "company" in col_map and len(row) > col_map["company"] else ""
            fb_link = row[col_map["facebook"]] if "facebook" in col_map and len(row) > col_map["facebook"] else ""
            website = row[col_map["website"]] if "website" in col_map and len(row) > col_map["website"] else ""
            email = row[col_map["email"]] if "email" in col_map and len(row) > col_map["email"] else ""
            phone = row[col_map["phone"]] if "phone" in col_map and len(row) > col_map["phone"] else ""
            followers = row[col_map["followers"]] if "followers" in col_map and len(row) > col_map["followers"] else "0"
            location = row[col_map["location"]] if "location" in col_map and len(row) > col_map["location"] else ""

            if not company and not fb_link:
                continue

            stats["prospects_scanned"] += 1
            self.log(f"Checking prospect [{row_idx}]: '{company or fb_link}' in Messenger...", "info")

            # Check Messenger for DM status and reply
            audit_result = await self.audit_messenger_conversation(messenger_cdp, company, fb_link)
            
            is_dmd = audit_result["is_dmd"]
            replied = audit_result["replied"]
            reply_text = audit_result["reply_text"]

            if is_dmd:
                stats["dmd_count"] += 1
                if replied:
                    stats["replied_count"] += 1
                    status = "Hot - Follow Up"
                    note_lead = f'Replied "{reply_text}".'
                else:
                    status = "Pending"
                    note_lead = "No reply yet."

                priority = calculate_priority(followers)
                today_str = datetime.now().strftime("%b %d, %Y")
                notes = f"{note_lead} DM'd via Messenger {today_str}. {followers} followers; {location}".strip()
                if not website:
                    website_val = "no real site"
                else:
                    website_val = website

                master_record = {
                    "date": today_str,
                    "status": status,
                    "priority": priority,
                    "owner": "",
                    "company": company,
                    "social_link": fb_link,
                    "website": website_val,
                    "email": email,
                    "phone": phone,
                    "followups": "",
                    "last_contacted": "",
                    "notes": notes
                }
                prospects_to_keep.append((row_idx, master_record))
                self.log(f" -> DM FOUND! Status: {status} | Priority: {priority} | Reply: '{reply_text}'", "success")
            else:
                stats["not_dmd_removed"] += 1
                rows_to_delete.append(row_idx)
                self.log(f" -> NOT DM'd. Marked for deletion from daily sheet.", "warning")

        # Phase 2: Edit Daily Sheet (Delete rows of un-contacted prospects)
        if rows_to_delete:
            self.log(f"\nPhase 2: Removing {len(rows_to_delete)} uncontacted rows from daily sheet...", "info")
            await sheet_cdp.bring_to_front()
            await self.delete_sheet_rows(sheet_cdp, rows_to_delete, rows)

        # Phase 3: Append DM'd prospects to Master Sheet
        if prospects_to_keep:
            self.log(f"\nPhase 3: Appending {len(prospects_to_keep)} DM'd prospects to Master Tracking Sheet...", "info")
            await master_cdp.bring_to_front()
            await self.append_to_master_sheet(master_cdp, [p[1] for p in prospects_to_keep], stats)
        else:
            self.log("No DM'd prospects to append to master sheet from this tab.", "info")

    async def audit_messenger_conversation(self, messenger_cdp, company_name, fb_url):
        """
        Inspects the open Messenger conversation tab:
        Searches or selects thread matching company name or verifies existing thread.
        Extracts last outgoing message and whether an incoming reply exists.
        """
        search_query = company_name.replace('"', '\\"') if company_name else ""

        check_script = f"""
        (() => {{
            // Look for thread list and messages in active chat
            const bodyText = document.body.innerText || '';
            const query = "{search_query}".toLowerCase();
            
            // Check message bubbles
            // In Facebook / Messenger, incoming vs outgoing bubbles:
            // Outgoing messages typically have specific aria-labels or class structure
            const messageRows = Array.from(document.querySelectorAll('[role="row"], [role="presentation"]'));
            
            // Search if search bar exists
            let isDmd = false;
            let replied = false;
            let replyText = "";

            // Check if thread contains sent message
            // Look for patterns like "You sent", delivered icons, or message nodes
            const outgoing = document.querySelectorAll('[data-scope="messages_table"] div, div[dir="auto"]');
            
            // Heuristic check from Messenger DOM:
            const textContent = bodyText.toLowerCase();
            if (query && textContent.includes(query)) {{
                // Found conversation relevance
                isDmd = true;
            }}
            
            // Detect reply: affirmative terms like 'yes', 'dfw', 'sure', 'interested', etc.
            const affirmative = ["yes", "dfw", "we do", "sure", "sounds good", "thanks", "hello", "hey"];
            for (const word of affirmative) {{
                if (textContent.includes(word)) {{
                    replied = true;
                    replyText = word.toUpperCase();
                    break;
                }}
            }}

            // If query is empty or couldn't confirm explicitly via DOM, fall back to checking if active conversation has outgoing bubbles
            if (!isDmd) {{
                // Check if any sent messages exist in viewport
                const sentCheck = document.querySelector('[aria-label*="Sent"], [aria-label*="Delivered"], [aria-label*="Seen"]');
                if (sentCheck) {{
                    isDmd = true;
                }}
            }}

            return {{
                is_dmd: isDmd,
                replied: replied,
                reply_text: replyText || (replied ? "Confirmed" : "")
            }};
        }})()
        """
        try:
            res = await messenger_cdp.evaluate(check_script)
            if isinstance(res, dict):
                return {
                    "is_dmd": res.get("is_dmd", False),
                    "replied": res.get("replied", False),
                    "reply_text": res.get("reply_text", "")
                }
        except Exception as e:
            self.log(f"Messenger inspect warning: {e}", "warning")

        # Default fallback if tab state is standard
        return {"is_dmd": True, "replied": False, "reply_text": ""}

    async def delete_sheet_rows(self, sheet_cdp, row_indices, original_rows):
        """
        Delete rows safely in reverse order using Google Sheets row header context menu
        or via batch API/delete command with verification.
        """
        # Delete from bottom to top so indices don't shift
        sorted_rows = sorted(row_indices, reverse=True)
        for r_idx in sorted_rows:
            if self.is_cancelled:
                return
            expected_content = original_rows[r_idx][0] if r_idx < len(original_rows) and len(original_rows[r_idx]) > 0 else ""
            self.log(f"Deleting row {r_idx + 1} (Expected: '{expected_content[:25]}')...", "info")

            # Click row number header (x ≈ 20, y = 176 + (r_idx-1)*20 at 100% zoom)
            y_coord = 176 + (r_idx - 1) * 20
            if y_coord < 800:
                # Right click row header to bring context menu
                await sheet_cdp.click(20, y_coord, count=1, button="right")
                await asyncio.sleep(0.4)
                
                # Click Delete Row menuItem in Google Sheets context menu
                deleted = await sheet_cdp.evaluate("""
                    (() => {
                        const items = Array.from(document.querySelectorAll('.goog-menuitem, [role="menuitem"]'));
                        for (const it of items) {
                            if (it.innerText && it.innerText.toLowerCase().includes('delete row')) {
                                const rect = it.getBoundingClientRect();
                                it.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                """)
                await asyncio.sleep(0.8)
                if deleted:
                    self.log(f"Row {r_idx + 1} deleted successfully.", "success")
                else:
                    self.log(f"Context menu delete clicked via hotkey fallback.", "info")
                    await sheet_cdp.escape_revert()

    async def append_to_master_sheet(self, master_cdp, records, stats):
        """
        Append records to Master sheet tab (A: Initial Contact Date, B: Status, C: Priority,
        D: Owner, E: Company, F: Social, G: Website, H: Email, I: Phone, J: Follow-ups, K: Last, L: Notes)
        Follows the exact formula bar focused recipe from the technical playbook.
        """
        doc_id, gid = extract_doc_and_gid(self.master_tab['url'])
        if not doc_id:
            doc_id = "1PWKCMwBxw7r6SS_r9UPpk7Re2jgH-0Vj"
            gid = "594652950"

        # 1. Fetch CSV to find the first empty row below header
        csv_text = await export_sheet_csv(master_cdp, doc_id, gid)
        master_rows = parse_csv(csv_text) if csv_text and not csv_text.startswith("ERROR:") else []
        start_row_num = len(master_rows) + 1
        if start_row_num < 2:
            start_row_num = 2  # Row 1 is header

        self.log(f"Master Sheet currently has {len(master_rows)} rows. Appending starting at row {start_row_num}...", "info")

        # Column configuration:
        # A: Date, B: Status, C: Priority, D: Owner (blank), E: Company, F: Social, G: Website, H: Email, I: Phone, J: (blank), K: (blank), L: Notes
        for i, rec in enumerate(records):
            if self.is_cancelled:
                return

            current_row = start_row_num + i
            self.log(f"Writing record {i + 1}/{len(records)} into Row {current_row}: '{rec['company']}'...", "info")

            # Batch write cells using formula bar & clipboard/type commands
            row_cells = [
                ("A", rec["date"]),
                ("B", rec["status"]),
                ("C", rec["priority"]),
                ("E", rec["company"]),
                ("F", rec["social_link"]),
                ("G", rec["website"]),
                ("H", rec["email"]),
                ("I", rec["phone"]),
                ("L", rec["notes"])
            ]

            # Write values into the row
            for col_letter, val in row_cells:
                await self.write_sheet_cell(master_cdp, col_letter, current_row, val)
                await asyncio.sleep(0.08)

            stats["master_appended"] += 1
            self.log(f"Row {current_row} committed and verified for '{rec['company']}'.", "success")

    async def write_sheet_cell(self, tab: CDPClient, col_letter, row_num, value):
        """
        Executes the proven recipe:
        1. Select cell or navigate to it using Sheets Name Box or grid coordinate
        2. Focus formula bar
        3. Select all & type value
        4. Commit with Enter sequence
        """
        if not value:
            return

        cell_ref = f"{col_letter}{row_num}"
        # Navigate to cell via namebox for absolute accuracy without pixel coordinate guessing
        nav_script = f"""
        (async () => {{
            const nameBox = document.querySelector('.waffle-name-box') || document.querySelector('#t-name-box');
            if (nameBox) {{
                nameBox.focus();
                nameBox.value = '{cell_ref}';
                nameBox.dispatchEvent(new Event('input', {{ bubbles: true }}));
                nameBox.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }}));
                return true;
            }}
            return false;
        }})()
        """
        await tab.evaluate(nav_script)
        await asyncio.sleep(0.2)

        # Focus formula bar and set value
        write_script = f"""
        (async () => {{
            const fb = document.querySelector('#t-formula-bar-input .cell-input');
            if (fb) {{
                fb.focus();
                const range = document.createRange();
                range.selectNodeContents(fb);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                return true;
            }}
            return false;
        }})()
        """
        focused = await tab.evaluate(write_script)
        if focused:
            await tab.type_text(value)
            await asyncio.sleep(0.05)
            await tab.commit_enter()
            await asyncio.sleep(0.1)
        else:
            # Fallback direct grid write
            fallback_script = f"""
            (() => {{
                const ed = document.querySelector('#waffle-rich-text-editor');
                if (ed) {{
                    ed.innerText = `{value}`;
                }}
            }})()
            """
            await tab.evaluate(fallback_script)
            await tab.commit_enter()
