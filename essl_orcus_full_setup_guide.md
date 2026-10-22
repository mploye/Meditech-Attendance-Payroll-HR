# eSSL AiFace-Orcus Full Setup Guide (Live HRMS)

## 1. Overview
Your Orcus device can only store **one** cloud/ADMS server address. To connect to the live backend while keeping eTimeTrackLite working on LAN, we use:
- **Cloud push (required):** Device pushes punches to our Render backend at `https://hrms-api-4trx.onrender.com` via the ZKTeco `/iclock` family. Our receiver is at root (no `/api/v1`).
- **LAN pull (optional but keeps existing):** eTimeTrackLite can still pull the device over TCP 4370 on your office network — this does **not** interfere with cloud push.

**Live URLs**
- Frontend: https://meditech-attendance-payroll-hr.vercel.app
- Backend: https://hrms-api-4trx.onrender.com
- Device: RAG8262801104 (registered as "Orcus Attendance")

**Credentials**
- Company Admin: admin@geneticsmeditech.com / Company@12345
- Super Admin: hr.genetics@gmail.com / Admin@12345

## 2. Device Network
1. Connect Orcus to your office network (same LAN as PC running eTimeTrackLite).
2. Get its IP from Menu → System → Network/Comm or from your DHCP table.
3. Ensure it has internet access (can reach `hrms-api-4trx.onrender.com` on port 443).

## 3. Register Device & Import Users in HRMS
1. Login to frontend (Company Admin).
2. Go to **Devices** → confirm "Orcus Attendance" (Serial `RAG8262801104`) is **ONLINE**.
3. Export users from **eTimeTrackLite** (Users/Employee list → Export CSV). Typical columns include `User ID`/`Enroll ID`, `User Name`, `Department`, `Designation`, `Email`, `Mobile`, `Join Date`, `Gender`.
4. On **Devices** page, open the device row → **Import Users** (or go to **Imports → Device Users** via API) and upload the CSV.
5. Our importer will auto-create employees, departments/designations if missing, generate `employee_code`, and map each `User ID` (device user ID) to the employee.
6. Go to **Employees → Device Mapping** (or open employee details) to verify: `device_user_id` matches the ID shown in eTimeTrackLite/Orcus.

## 4. Configure Orcus ADMS/Cloud Server (Single Address)
On the Orcus keypad/menu:
1. Menu → Comm/Communication → Cloud Server (or **ADMS** / **Push Settings** depending on firmware).
2. Set:
   - **Server Address:** `hrms-api-4trx.onrender.com`
   - **Server Port:** `443`
   - **Protocol:** **HTTPS** (or HTTP only if firmware doesn't support — try HTTPS first; port 443)
   - **Enable Push / Real-time Push:** **ON**
3. Save and restart comms if prompted.

> Note: eTimeTrackLite uses direct TCP pull (port 4370) — leave that untouched.

## 4b. Your current device settings (snapshot from your Orcus screen) & what to change

| Setting | Current value | Action |
|---|---|---|
| Communication Protocol | PUSH Protocol | Keep |
| Device Type | T&A PUSH | Keep |
| Wi-Fi | Enabled | Keep |
| Connected Wi-Fi | GENETIC-13 | Keep (must have internet) |
| SSH | Enabled | Optional — leave as is (or OFF if you want to harden) |
| User ID Masking | **Enabled** | **Turn OFF** — masking hides/obfuscates user IDs and can break punch→employee mapping |
| Ethernet IP | 192.168.0.201 (static) | **Enable DHCP** if Wi-Fi subnet isn't 192.168.0.x |
| Subnet Mask | 255.255.255.0 | Auto with DHCP |
| Gateway | 192.168.0.1 | Must be reachable on GENETIC-13 network |
| DHCP | Disabled | **Enable** (safer; static + Wi-Fi often causes no-internet) |
| TCP communication port | 4370 | Keep — that's the LAN pull port for eTimeTrackLite |
| PC Connection HTTPS | Enabled | Keep — that's for PC software, **not** the ADMS push |

### Values to enter in ADMS / Cloud Server (this is the missing piece)
The snapshot does **not** show a server address/port — that's why our backend still shows `last_seen: None` (zero punches received).

- **Server Address:** `hrms-api-4trx.onrender.com`  (or IP `216.24.57.16`)
- **Server Port:** `443`
- **Protocol / HTTPS:** ON
- **Enable / Auto-push / Real-time:** ON
- **Proxy:** OFF / blank
- Save → **reboot**

> If the Orcus rejects the hostname, use `216.24.57.16`. If it rejects HTTPS, use Port `80` + HTTPS OFF as a fallback, then re-test.

### Why this matters
- Port **4370** is only for direct LAN pull (eTimeTrackLite). It is **not** the ADMS/HTTPS push port.
- `192.168.0.201` is your LAN address — the device pushes **out** to the cloud, so the LAN IP does not need to be reachable from our server.

## 5. Test Cloud Push
1. On Orcus, punch IN/OUT once.
2. Wait 10–30 seconds (device batches pushes).
3. Check in HRMS: **Attendance → Logs** (filter by date/device). You should see the punch appear with `Source: DEVICE`, correct time (converted to IST/your company timezone).
4. Also verify via API:
```bash
curl -H "Authorization: Bearer <token>" "https://hrms-api-4trx.onrender.com/api/v1/attendance/logs?limit=5"
```

## 6. Multi-Break Calculation (How it works)
Our backend computes breaks in this order:
1. **Logged breaks** (`break_logs`) — if employees end breaks via web/app
2. **Punched breaks** — for multi-punch days (OUT→IN gaps count as breaks). Example: 09:00 I, 10:10 O, 10:15 I → 5 min break.
3. **Scheduled budget** — shift's scheduled breaks/templates

The example you gave: 09:00 I, 10:10 O, 10:15 I, 11:30 O, 11:35 I, 13:00 O, 13:45 I, 14:10 O, 14:17 I, 18:00 O → breaks **62 min**, net **7h58** (478 min) — this is computed automatically.

## 7. Troubleshooting
- **PUNCHES NOT APPEARING**: Check Orcus comm logs (if any) — confirm server address/port/HTTPS. Verify internet.
- **"UNKNOWN SERIAL" error**: Device serial must be `RAG8262801104` and registered in HRMS as ONLINE.
- **WRONG EMPLOYEE**: Ensure `device_user_id` in mapping matches Orcus User ID exactly (case/spacing sensitive).
- **etimetracklite still works**: LAN pull is independent — no change needed.
- **Mock mode**: Live backend has `ESSL_MOCK_MODE=true` (outgoing ESSL API stubs) — does **not** affect inbound `/iclock/*` pushes.

## 8. Quick API Checks
- Handshake: `GET https://hrms-api-4trx.onrender.com/iclock/getrequest?SN=RAG8262801104` → `200` empty
- Devices: `GET /api/v1/devices/` (auth)
- Mappings: `GET /api/v1/imports/device-users/8623aaf9-8d8a-4d39-a6c9-5f490af5b6eb` (auth)

---

**Done**: Device registered, `/iclock/cdata` live, multi-punch break calc live, CSV import live. After pushing real punches from Orcus, share timestamps if anything looks off — I’ll verify instantly.