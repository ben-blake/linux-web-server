# Demo Script

**Total demo time:** ~16 minutes (4 sections x ~4 min each)
**URL:** your ngrok URL, e.g. `https://abc123.ngrok-free.app`

Before demo: server is running, ngrok is running, browser is open to the login page, test files are ready in `test_files/`.

---

## Section 1 — User Management (Ben Blake, ~4 min)

**Start:** Login page is visible in the browser.

1. "We'll start by logging in as the default admin account."
   - Enter `admin` / `admin`, click Log In.
   - Land on the dashboard. Point out the user count, file count, and last backup.

2. "The first thing I'll show is creating a new user with limited access."
   - Navigate to Users in the sidebar.
   - Click Create User.
   - Username: `ben`, Password: `ben`, Role: User, Permissions: Read + Write + Edit.
   - Submit. Show the success flash and the user in the list.

3. "Now I'll also create a read-only user that will be used demonstrate how permissions restrict access when we move onto the files demonstration."
   - Click Create User again.
   - Username: `viewer`, Password: `viewer`, Role: User, Permissions: Read only.
   - Submit.

4. "I can edit an existing user's role and permissions at any time."
   - Click Edit next to `ben`.
   - Change Role to Admin, add all permissions, save.
   - Show the updated row in the list.
   - Edit again and change back to User role.

5. "Let me show what happens when a non-admin tries to access the user list."
   - Log out. Log in as `viewer` / `viewer`.
   - Try to visit `/users/` manually by typing it in the URL bar.
   - Show the 403 Forbidden page.
   - Log back out.

6. "Finally, a user can change their own password from their profile."
   - Log in as `viewer`.
   - Go to My Profile in the sidebar.
   - Enter current password `viewer`, new password `viewer1`, save.
   - Show the success flash.
   - Log back out. Log back in as `viewer` / `viewer1` to confirm it works.
   - Log out and log back in as `admin` / `admin` to continue.

---

## Section 2 — File Management (Rasagyna Peddapalli, ~4 min)

**Start:** Logged in as admin, on the dashboard.

1. "The file manager lets any user with read permission browse the NAS storage."
   - Click Files in the sidebar.
   - Show the empty root. Point out the disk usage stats in the header.

2. "I'll create the folder structure first, then upload files into it."
   - Create folder: `documents`.
   - Navigate into `documents`. Create folder: `reports`.
   - Navigate back to root using the breadcrumb. Create folder: `media`.

3. "Now let's upload some files."
   - Navigate into `documents/reports`.
   - Upload `test_files/documents/reports/q1-summary.txt`.
   - Upload `test_files/documents/reports/q2-summary.txt`.
   - Show both files in the listing with sizes and dates.
   - Navigate into `media`.
   - Upload `test_files/media/screenshot.png`.

4. "Downloading is a single click."
   - Click Download next to `q1-summary.txt`.
   - Show the file download in the browser.

5. "Renaming works on both files and folders."
   - Rename `q1-summary.txt` to `q1-report.txt`.
   - Show the success flash and updated name.
   - Navigate back to root. Rename `documents` to `docs`.
   - Navigate into `docs/reports` to show the file is still there.

6. "All paths are validated server-side. Let me show the path traversal protection."
   - In the URL bar, manually type `?path=../etc` after `/files/`.
   - Show the flash error and redirect to root.

7. "Now let me show what a read-only user sees from that viewer account that Ben made earlier."
   - Log out. Log in as `viewer` / `viewer1`.
   - Go to Files. Show they can browse and see the files.
   - Show that the Upload form, New Folder, Rename, and Delete buttons are hidden.
   - Log back out. Log back in as admin.

8. "Deleting removes the item from both the filesystem and the database."
   - Navigate into `docs/reports`.
   - Delete `q2-report.txt` (the renamed version or the second file).
   - Show the success flash and the file gone from the listing.

---

## Section 3 — System Monitoring (Bhavya Harshitha Chennu, ~4 min)

**Start:** Logged in as admin, on the dashboard.

1. "The monitoring page shows live system stats for the host running the NAS."
   - Click Monitor in the sidebar.
   - Point out the three cards: CPU, Memory, Disk.
   - Note the current values and the visual progress bars.

2. "These values update automatically every 10 seconds without a full page reload."
   - Watch the page for one update cycle (10 seconds).
   - Show a value change — CPU in particular will fluctuate.
   - "We replaced the original hard refresh with a JavaScript fetch call to a
JSON endpoint. The page stays stable and only the numbers change."

3. "The logs page shows the last 100 lines of the system log."
   - Click View System Logs.
   - Scroll through the entries. Point out timestamps and log levels.
   - "These are read-only — there's no way to clear or write logs from the UI.
     This ensures visibility without risk."

4. "Any logged-in user can see the monitor, not just admins."
   - Log out, log in as `viewer` / `viewer1`, go to Monitor — stats are visible.
   - Log back out and log back in as `admin` / `admin`.

---

## Section 4 — Backup & Restore (Mukunda Chakravartula, ~4 min)

**Start:** Logged in as `admin` / `admin`, files already in /srv/nas from Section 2.

1. "The backup system creates a compressed snapshot of everything in NAS storage."
   - Click Backups in the sidebar.
   - Show the empty backup list.
   - Click Create Backup Now.
   - Show the success flash and the backup entry with its real size in KB.

2. "You can download the backup to store an extra copy if you want. In a production system this would be stored in a seperate server."

3. "We can also schedule backups to run automatically."
   - Click Configure Schedule.
   - Select Every 1 hour, click Save Schedule.
   - Show the success flash, redirect to the backup list showing the scheduled job.
   - "This schedule survives a server restart.
     It's saved to the database and restored automatically when the app starts."

4. "Now let's test the restore."
   - Go back to Files. Delete `q1-report.txt` to simulate data loss.
   - Confirm it's gone.
   - Go back to Backups.
   - Click Restore next to the backup we just created.
   - Confirm the dialog.
   - Show the success flash.
   - Go to Files and navigate into `docs/reports`.
   - Show `q1-report.txt` is back.

5. "Backups can be deleted when they're no longer needed."
   - Go back to Backups.
   - Click Delete on the backup.
   - Show the success flash and empty list.
   - Verify on the VM: `ls /srv/nas-backups/` — directory is empty.

6. "Only admins can access the backup section."
   - Log out, log in as `viewer` / `viewer1`, try to visit `/backup/`.
   - Show the 403 Forbidden page.

---

## Wrap-Up (30 seconds)

- Switch back to the presentation slides for the Summary slide.
- "142 automated tests, all passing. Four independent modules built and integrated
  by four people in one Flask application. Happy to take questions."
