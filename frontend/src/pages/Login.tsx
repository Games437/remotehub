import { useState } from "react";
import { Link } from "react-router-dom";
import { useConfirm2FASetup, useLogin } from "../hooks/useAuth";

interface SetupChallenge {
  setup_token: string;
  secret: string;
  otpauth_url: string;
}

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const login = useLogin();

  // Set only when the backend responds requires_2fa_setup=true — i.e. this
  // account has never finished 2FA enrollment. While this is non-null we
  // show the setup screen instead of having actually logged the user in.
  const [setupChallenge, setSetupChallenge] = useState<SetupChallenge | null>(null);
  const [setupCode, setSetupCode] = useState("");
  const confirmSetup = useConfirm2FASetup();

  function submitLogin(e: React.FormEvent) {
    e.preventDefault();
    login.mutate(
      { email, password, totp_code: totp || undefined },
      {
        onSuccess: (data) => {
          if (data.requires_2fa_setup && data.setup_token && data.secret && data.otpauth_url) {
            setSetupChallenge({
              setup_token: data.setup_token,
              secret: data.secret,
              otpauth_url: data.otpauth_url,
            });
          }
          // Normal case (no 2FA setup needed) is handled inside useLogin's
          // own onSuccess, which saves tokens and navigates away.
        },
      }
    );
  }

  function submitSetupConfirm(e: React.FormEvent) {
    e.preventDefault();
    if (!setupChallenge) return;
    confirmSetup.mutate({ setup_token: setupChallenge.setup_token, totp_code: setupCode });
  }

  if (setupChallenge) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <form
          className="w-full max-w-sm bg-panel border border-line rounded-xl p-8"
          onSubmit={submitSetupConfirm}
        >
          <h1 className="text-xl font-semibold mb-1">ตั้งค่ายืนยันตัวตน 2 ขั้นตอน</h1>
          <p className="text-muted text-sm mb-6">
            บัญชีนี้ยังไม่ได้ตั้งค่า 2FA ทุกบัญชีต้องเปิดใช้งานก่อนเข้าใช้งานได้
          </p>

          <div className="mb-4">
            <p className="text-sm text-muted mb-2">
              1. เปิดแอปยืนยันตัวตน (Google Authenticator, Authy ฯลฯ) แล้วเพิ่มบัญชีใหม่
              ด้วยการกรอกรหัสลับนี้ด้วยตนเอง (Time-based, 6 หลัก):
            </p>
            <div className="bg-base border border-line rounded-lg px-3 py-2 mono text-sm break-all select-all">
              {setupChallenge.secret}
            </div>
          </div>

          <div className="mb-4">
            <p className="text-xs text-muted">
              หรือถ้าแอปรองรับการกรอกลิงก์โดยตรง ใช้ค่านี้:
            </p>
            <div className="bg-base border border-line rounded-lg px-3 py-2 mono text-xs break-all select-all mt-1">
              {setupChallenge.otpauth_url}
            </div>
          </div>

          <label className="block text-sm text-muted mb-1">
            2. กรอกรหัส 6 หลักที่แอปแสดงขึ้นมา
          </label>
          <input
            autoFocus
            className="w-full mb-2 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent mono"
            placeholder="123456"
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            value={setupCode}
            onChange={(e) => setSetupCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            required
          />

          {confirmSetup.isError && (
            <p className="text-danger text-sm mb-2">รหัส 6 หลักไม่ถูกต้อง หรือรหัสลับหมดอายุแล้ว</p>
          )}

          <button
            className="w-full bg-accent hover:opacity-90 transition rounded-lg py-2 font-medium mt-4"
            type="submit"
            disabled={confirmSetup.isPending || setupCode.length !== 6}
          >
            {confirmSetup.isPending ? "กำลังยืนยัน..." : "ยืนยันและเข้าสู่ระบบ"}
          </button>

          <button
            type="button"
            className="w-full text-sm text-muted mt-3"
            onClick={() => {
              setSetupChallenge(null);
              setSetupCode("");
            }}
          >
            ยกเลิกและกลับไปล็อกอินใหม่
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form className="w-full max-w-sm bg-panel border border-line rounded-xl p-8" onSubmit={submitLogin}>
        <h1 className="text-xl font-semibold mb-1">RemoteHub</h1>
        <p className="text-muted text-sm mb-6">เข้าสู่ระบบเพื่อจัดการเครื่องคอมพิวเตอร์ของคุณ</p>

        <label className="block text-sm text-muted mb-1">อีเมล</label>
        <input
          className="w-full mb-4 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <label className="block text-sm text-muted mb-1">รหัสผ่าน</label>
        <input
          className="w-full mb-4 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <label className="block text-sm text-muted mb-1">รหัส 2FA (6 หลัก)</label>
        <input
          className="w-full mb-1 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent mono"
          placeholder="123456"
          inputMode="numeric"
          pattern="\d{6}"
          maxLength={6}
          value={totp}
          onChange={(e) => setTotp(e.target.value.replace(/\D/g, "").slice(0, 6))}
        />
        <p className="text-xs text-muted mb-6">
          เว้นว่างไว้ได้หากนี่เป็นการล็อกอินครั้งแรก — ระบบจะพาไปตั้งค่าให้เอง
        </p>

        {login.isError && (
          <p className="text-danger text-sm mb-4">อีเมล รหัสผ่าน หรือรหัส 2FA ไม่ถูกต้อง</p>
        )}

        <button
          className="w-full bg-accent hover:opacity-90 transition rounded-lg py-2 font-medium"
          type="submit"
          disabled={login.isPending}
        >
          {login.isPending ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่ระบบ"}
        </button>

        <p className="text-muted text-sm mt-6 text-center">
          ยังไม่มีบัญชี? <Link to="/register" className="text-accent">สร้างบัญชีใหม่</Link>
        </p>
      </form>
    </div>
  );
}
