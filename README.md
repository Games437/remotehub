# RemoteHub

Remote Computer Management Platform — React + FastAPI + WebSocket + PostgreSQL
พร้อม Agent (Python) สำหรับควบคุมเครื่องปลายทาง

## โครงสร้างโปรเจกต์

```
remotehub/
├── backend/        FastAPI server (auth, machines, commands, websocket)
├── frontend/        React + TypeScript + Tailwind dashboard
├── agent/            Python agent ที่รันบนเครื่องปลายทาง (ออกแบบสำหรับ Windows)
├── docker-compose.yml
└── .env.example
```

## รันแบบ local (development)

**1. Backend + Database**

```bash
cp .env.example .env      # แล้วแก้ JWT_SECRET เป็นค่าสุ่มยาวๆ
docker compose up --build postgres redis backend
```

Backend จะรันที่ `http://localhost:8000` — เอกสาร API (Swagger) ดูได้ที่
`http://localhost:8000/docs`

**2. Frontend**

```bash
cd frontend
npm install
npm run dev
```

เปิด `http://localhost:5173` แล้วสมัครสมาชิก (Register) ก่อนใช้งาน

**3. Agent (ติดตั้งบนเครื่องที่ต้องการควบคุม)**

```bash
cd agent
pip install -r requirements.txt

# 1) ในหน้าเว็บ กด "Add machine" จะได้รหัสจับคู่ เช่น ABCD-EFGH
# 2) รันบนเครื่องปลายทาง:
python -m agent.client pair ABCD-EFGH

# 3) จากนั้นรันแบบค้างไว้ตลอด (ทำเป็น Windows Service / Scheduled Task ในการใช้งานจริง):
python -m agent.client run
```

เมื่อ pairing สำเร็จ เครื่องจะขึ้นสถานะ Online ในหน้า Dashboard ทันที

## แผนที่ระบบความปลอดภัย 10 ชั้น → โค้ด

| ชั้น | สิ่งที่ทำ | อยู่ที่ไฟล์ |
|---|---|---|
| 1. HTTPS | เทอร์มิเนต TLS ที่ reverse proxy หน้าระบบ (ดูหัวข้อ Production ด้านล่าง) | `frontend/nginx.conf`, deployment note |
| 2. JWT | Access token อายุ 15 นาที, Refresh token อายุ 30 วัน | `backend/app/core/security.py` |
| 3. Agent Token | Machine ID + secret 256-bit, พิสูจน์ตัวตนด้วย HMAC challenge (ไม่ส่ง secret ผ่านสาย) | `backend/app/websocket/agent_ws.py`, `agent/security.py` |
| 4. Device Pairing | สร้างรหัสจับคู่ชั่วคราวจากเว็บ แล้วให้ agent กรอกรหัสเพื่อผูกเครื่อง | `backend/app/api/v1/machines.py` (`/pair/generate-code`, `/pair/redeem`) |
| 5. Command Signature | ทุกคำสั่งเซ็นด้วย HMAC(machine_secret, command+timestamp+nonce) กัน replay/ปลอมคำสั่ง | `backend/app/core/security.py`, `backend/app/api/v1/commands.py`, `agent/security.py` |
| 6. Role | Owner / Admin / Member / Viewer ต่อเครื่อง | `backend/app/models/machine.py`, `backend/app/api/deps.py::require_role` |
| 7. Audit Log | บันทึกทุก event สำคัญ (login, pairing, ส่งคำสั่ง, เปลี่ยนสิทธิ์) แบบ append-only | `backend/app/services/audit.py` |
| 8. Rate Limit | จำกัด 20 req/นาที ต่อ user+IP (ปรับได้ผ่าน `RATE_LIMIT_PER_MINUTE`) | `backend/app/core/rate_limit.py` |
| 9. Password | Argon2id (bcrypt เป็น fallback verifier) | `backend/app/core/security.py` |
| 10. 2FA | TOTP มาตรฐาน ใช้กับ Google/Microsoft Authenticator ได้ | `backend/app/api/v1/auth.py` (`/2fa/enable`, `/2fa/confirm`) |

## ข้อควรทำก่อนขึ้น production จริง

1. **TLS** — ใส่ reverse proxy (Caddy หรือ nginx+certbot) หน้า `backend`/`frontend`
   เพื่อออกใบรับรองอัตโนมัติและบังคับ HTTPS ทั้งหมด รวมถึง WebSocket (`wss://`)
2. **Migration** — ตอนนี้ backend ใช้ `Base.metadata.create_all()` ตอน startup
   เพื่อความง่ายตอน dev เท่านั้น ให้เปลี่ยนมาใช้ Alembic (`alembic upgrade head`)
   เป็นขั้นตอน deploy แยกต่างหาก
3. **เข้ารหัส machine secret ที่เก็บใน DB** — ตอนนี้เก็บเป็น plaintext ในคอลัมน์
   `machines.secret` เพื่อให้โค้ด HMAC อ่านง่าย ให้เปลี่ยนไปใช้ envelope encryption
   (เช่น AWS KMS / age) ก่อนใช้งานจริง
4. **Refresh token revocation** — เพิ่ม denylist ของ `jti` ใน Redis
   เพื่อให้ logout / เปลี่ยนรหัสผ่านสามารถเพิกถอน refresh token เก่าได้ทันที
5. **หลายเครื่อง backend (scale-out)** — `ConnectionManager` ตอนนี้เก็บ
   การเชื่อมต่อ websocket ไว้ใน memory ของ process เดียว ถ้ามีมากกว่า 1 replica
   ให้เปลี่ยนไปใช้ Redis pub/sub ตามที่คอมเมนต์ไว้ใน
   `backend/app/websocket/manager.py`
6. **Screenshot storage** — ตอนนี้ส่งภาพกลับเป็น base64 ผ่าน websocket โดยตรง
   (ใช้ได้กับ dev/เล็กๆ) ให้เปลี่ยนไปอัปโหลดขึ้น object storage (S3/R2) ด้วย
   pre-signed URL สำหรับการใช้งานจริง — ดูคอมเมนต์ใน
   `agent/commands/screenshot.py`
7. **อีเมลจริง** — `backend/app/services/email.py` ตอนนี้แค่ log ข้อความ
   ให้เปลี่ยนไปต่อกับผู้ให้บริการอีเมลจริง (SES/Postmark/SendGrid)

## คำสั่งที่ agent รองรับตอนนี้

`open_website`, `open_program`, `play_music`, `shutdown`, `restart`, `sleep`,
`lock`, `screenshot`, `notification`, `clipboard`

เพิ่มคำสั่งใหม่ได้โดย: (1) เพิ่ม enum ใน `backend/app/models/command.py::CommandType`,
(2) เขียนฟังก์ชันจัดการใน `agent/commands/`, (3) ลงทะเบียนใน
`agent/commands/__init__.py::DISPATCH`
