import { Link } from "react-router-dom";

export default function Help() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">ช่วยเหลือ &amp; ดาวน์โหลด</h1>
        <Link to="/" className="text-sm text-accent">
          กลับไปหน้า Dashboard
        </Link>
      </div>

      {/* --- ดาวน์โหลด ------------------------------------------------- */}
      <section className="bg-panel border border-line rounded-xl p-6">
        <h2 className="font-medium mb-2">1. ดาวน์โหลดตัว Agent (Windows)</h2>
        <p className="text-sm text-muted mb-4">
          ติดตั้งโปรแกรมนี้บนทุกเครื่องคอมพิวเตอร์ที่ต้องการควบคุมจากระยะไกล
          ตัว Agent จะทำงานเงียบๆ อยู่เบื้องหลัง และจะทำตามคำสั่งที่ส่งมาจาก
          บัญชีของคุณเท่านั้น
        </p>
        <a
          href="/downloads/RemoteHubAgent.exe"
          download
          className="inline-block bg-accent rounded-lg px-4 py-2 text-sm font-medium"
        >
          ดาวน์โหลด RemoteHubAgent.exe
        </a>
        <p className="text-xs text-muted mt-3">
          รองรับเฉพาะ Windows 10/11 เท่านั้นในตอนนี้ เบราว์เซอร์อาจแจ้งเตือนว่า
          ไฟล์นี้ไม่ค่อยถูกดาวน์โหลดบ่อย — เป็นเรื่องปกติสำหรับเครื่องมือใหม่ที่
          ยังไม่ได้เซ็นใบรับรอง (unsigned) ให้เลือก "Keep" หรือ "Download anyway"
          เพื่อดำเนินการต่อ
        </p>
      </section>

      {/* --- การตั้งค่า agent --------------------------------------- */}
      <section className="bg-panel border border-line rounded-xl p-6">
        <h2 className="font-medium mb-2">2. ตั้งค่า Agent บนเครื่องปลายทาง</h2>
        <ol className="list-decimal list-inside text-sm space-y-2 text-muted">
          <li>เปิดโปรแกรม <span className="mono text-text">RemoteHubAgent.exe</span> บนเครื่องนั้น</li>
          <li>
            หน้าต่างล็อกอินเล็กๆ จะเปิดขึ้นมา — ล็อกอินด้วย{" "}
            <strong className="text-text">อีเมลและรหัสผ่านเดียวกัน</strong>{" "}
            กับที่ใช้บนเว็บไซต์นี้
          </li>
          <li>
            ถ้าเป็นการล็อกอินครั้งแรกจากเครื่องนี้ เครื่องจะลงทะเบียนตัวเองเป็น
            เครื่องใหม่โดยอัตโนมัติ — ไม่ต้องใช้ pairing code
          </li>
          <li>
            หลังล็อกอินแล้ว สามารถย่อหน้าต่างหรือปิดลง tray ได้ ตัว Agent จะยังทำงาน
            ต่อเบื้องหลัง และเชื่อมต่อใหม่อัตโนมัติหากอินเทอร์เน็ตหลุด
          </li>
          <li>
            กลับมาที่หน้า Dashboard — เครื่องควรขึ้นจุดสีเขียว "Online" ภายในไม่กี่วินาที
          </li>
        </ol>
        <p className="text-xs text-muted mt-4">
          ล็อกอินซ้ำบนเครื่องเดิมภายหลังจะแค่เชื่อมต่อใหม่เท่านั้น — จะไม่สร้างรายการ
          เครื่องซ้ำซ้อน
        </p>
      </section>

      {/* --- การใช้งาน dashboard ----------------------------------------- */}
      <section className="bg-panel border border-line rounded-xl p-6">
        <h2 className="font-medium mb-2">3. การใช้งาน Dashboard</h2>
        <div className="space-y-4 text-sm">
          <div>
            <p className="font-medium text-text">การส่งคำสั่ง</p>
            <p className="text-muted">
              การ์ดของแต่ละเครื่องแบ่งปุ่มคำสั่งเป็น 3 หมวดแบบ tab —{" "}
              <strong className="text-text">Actions</strong>,{" "}
              <strong className="text-text">Status</strong>, และ{" "}
              <strong className="text-text">Power</strong> — คลิกชื่อหมวดเพื่อสลับดู
              ปุ่มในหมวดนั้น เครื่องต้องขึ้นสถานะ "Online" ก่อนถึงจะส่งคำสั่งได้ —
              ถ้ายังออฟไลน์อยู่ปุ่มจะกดไม่ได้
            </p>
          </div>

          <div>
            <p className="font-medium text-text">คำสั่งที่ทำให้เครื่องมีการเปลี่ยนแปลง</p>
            <ul className="list-disc list-inside text-muted space-y-1 mt-1">
              <li><span className="text-text">Open website</span> — เปิดเว็บไซต์ตาม URL ที่กรอก</li>
              <li><span className="text-text">Open program</span> — เปิดโปรแกรมตาม path ที่กรอก (เช่น <span className="mono">C:\Path\To\App.exe</span>)</li>
              <li><span className="text-text">Screenshot</span> — ถ่ายภาพหน้าจอปัจจุบัน แล้วดาวน์โหลดมาที่เครื่องคุณอัตโนมัติ ไม่เก็บไว้บนเซิร์ฟเวอร์</li>
              <li><span className="text-text">Send message</span> — เด้งกล่องข้อความสไตล์ RemoteHub ค้างบนหน้าจอปลายทางจนกว่าจะกด OK พร้อมป้าย "Message from Admin" ให้รู้ว่าใครส่ง ต่างจาก notification ทั่วไปที่หายไปเองโดยไม่รู้ว่ามีคนเห็นหรือเปล่า</li>
              <li><span className="text-text">Lock</span> — ล็อกหน้าจอเครื่องปลายทางทันที (มี modal ยืนยันก่อนส่ง)</li>
              <li><span className="text-text">Sleep</span> — สั่งให้เครื่องเข้าโหมดพักเครื่อง (sleep) (มี modal ยืนยันก่อนส่ง)</li>
              <li><span className="text-text">Restart / Shutdown</span> — รีสตาร์ท/ปิดเครื่อง (มีช่วงเวลาเผื่อไว้ ดูหัวข้อด้านล่าง)</li>
              <li><span className="text-text">Kill process</span> — ปิดโปรแกรมที่ค้าง/แฮงค์จากระยะไกล วิธีง่ายสุดคือกดปุ่ม "Kill" ตรงแถวโปรแกรมนั้นในผลลัพธ์ของ <span className="text-text">Processes</span> เลย (ระบุ PID ให้อัตโนมัติ) หรือพิมพ์ PID เองก็ได้ถ้ารู้อยู่แล้ว มี modal ยืนยันก่อนส่งเสมอ</li>
            </ul>
          </div>

          <div>
            <p className="font-medium text-text">ไม่มีการดูหน้าจอสด — ใช้คำสั่งเหล่านี้แทนได้</p>
            <ul className="list-disc list-inside text-muted space-y-1 mt-1">
              <li>
                <span className="text-text">Idle time</span> — บอกว่าไม่มีใครแตะคีย์บอร์ด/เมาส์
                บนเครื่องนั้นมานานแค่ไหนแล้ว ใช้เช็คก่อนสั่ง Shutdown/Restart
                ถ้าไม่แน่ใจว่ามีคนอยู่หน้าเครื่องหรือไม่
              </li>
              <li>
                <span className="text-text">Processes</span> — แสดงรายการโปรแกรมที่กำลังรันอยู่
                จัดกลุ่มตามชื่อโปรแกรม (เช่น Chrome ที่เปิดหลาย process จะรวมเป็นแถวเดียว
                พร้อมบอกจำนวน ×N) เรียงตามการใช้ memory มากไปน้อย โปรแกรมพื้นฐานของ
                Windows ที่ใช้ resource น้อยจะถูกซ่อนไว้เพื่อไม่ให้รายการรก
              </li>
              <li>
                <span className="text-text">Active window</span> — บอกว่าตอนนี้ผู้ใช้กำลังโฟกัส
                อยู่ที่หน้าต่างโปรแกรมไหน
              </li>
              <li>
                <span className="text-text">Open windows</span> — แสดงรายการหน้าต่างทั้งหมดที่
                เปิดค้างอยู่ (ไม่ใช่แค่ตัวที่โฟกัส) ใช้เช็คว่ามีงานที่ยังไม่ได้ save ค้างอยู่
                ก่อนสั่ง Shutdown/Restart
              </li>
              <li>
                <span className="text-text">Network status</span> — เช็คว่าเครื่องปลายทางยังต่อ
                อินเทอร์เน็ตได้ปกติไหม พร้อมค่า latency คร่าวๆ
              </li>
              <li>
                <span className="text-text">System info</span> — สเปคเครื่อง (CPU รุ่นจริง, การ์ดจอ,
                RAM, OS, uptime) พร้อมพื้นที่ดิสก์แต่ละไดรฟ์ ข้อมูลนี้แทบไม่เปลี่ยน ไม่ต้องเช็คบ่อย
              </li>
            </ul>
            <p className="text-muted text-xs mt-2">
              ปุ่มกลุ่มนี้กดซ้ำที่ปุ่มเดิมอีกครั้งเพื่อ<strong className="text-text">ย่อผลลัพธ์ที่แสดงอยู่</strong>ได้เลย
              โดยไม่ต้องกดปุ่ม Close — กดซ้ำอีกทีถัดไปจะรันคำสั่งใหม่และแสดงผลอีกครั้ง
            </p>
          </div>

          <div>
            <p className="font-medium text-text">Shutdown / Restart มีช่วงเวลาปลอดภัยก่อนทำจริง</p>
            <p className="text-muted">
              เมื่อกดคำสั่งใดคำสั่งหนึ่ง เครื่องปลายทางจะได้รับการแจ้งเตือนล่วงหน้า
              60 วินาที (ขึ้นเป็น notification บนหน้าจอนั้น) ก่อนจะปิด/รีสตาร์ทจริง
              — เพียงพอให้ผู้ใช้ที่อยู่หน้าเครื่อง save งานทัน ระหว่างช่วงเวลานี้จะมีปุ่ม{" "}
              <span className="text-danger">Cancel</span> ขึ้นมาบนการ์ด พร้อมตัวเลขนับถอยหลัง
              วินาทีจริงให้เห็น หากเปลี่ยนใจ
            </p>
          </div>

          <div>
            <p className="font-medium text-text">หากคำสั่งล้มเหลว</p>
            <p className="text-muted">
              การ์ดจะแสดง error ที่ agent รายงานกลับมา และส่วนใหญ่จะมีลิงก์
              "Download screen at time of failure" ขึ้นมาด้วย — เป็นภาพหน้าจอที่
              ถ่ายอัตโนมัติ ณ ขณะที่คำสั่งล้มเหลว ทำให้เห็นว่าหน้าจอเป็นอย่างไร
              โดยไม่ต้องสั่ง Screenshot ล่วงหน้าเอง
            </p>
          </div>

          <div>
            <p className="font-medium text-text">History</p>
            <p className="text-muted">
              ปุ่ม History อยู่ข้างๆ ปุ่มคำสั่งต่างๆ กดแล้วโชว์{" "}
              <strong className="text-text">ประวัติคำสั่งทั้งหมดที่เคยส่งไปเครื่องนั้น</strong>{" "}
              (ชื่อคำสั่ง, สถานะ, เวลา) แบ่งหน้าทีละ 20 รายการเลื่อนดูก่อนหน้า/ถัดไปได้
              — ไม่ได้ส่งคำสั่งอะไรไปที่เครื่อง แค่ดึงประวัติที่มีอยู่แล้วมาโชว์ กดปุ่มซ้ำ
              เพื่อย่อได้เหมือนปุ่มกลุ่ม Idle time/Processes ด้านบน
            </p>
          </div>

          <div>
            <p className="font-medium text-text">Activity log</p>
            <p className="text-muted">
              หน้า <Link to="/activity" className="text-accent">Activity log</Link>{" "}
              บันทึกทุกการล็อกอินและทุกคำสั่งที่คุณเคยส่ง พร้อมเวลาที่เกิดขึ้น —
              ใช้เป็นหลักฐานตรวจสอบย้อนหลังว่า "เกิดอะไรขึ้นจริง" ได้
            </p>
          </div>
        </div>
      </section>

      {/* --- แก้ปัญหาเบื้องต้น --------------------------------------------- */}
      <section className="bg-panel border border-line rounded-xl p-6">
        <h2 className="font-medium mb-2">แก้ปัญหาเบื้องต้น</h2>
        <div className="space-y-3 text-sm">
          <div>
            <p className="font-medium text-text">เครื่องขึ้น Offline ทั้งที่ agent กำลังรันอยู่</p>
            <p className="text-muted">
              เช็คว่าคอมพิวเตอร์เครื่องนั้นต่ออินเทอร์เน็ตอยู่ และหน้าต่าง agent ไม่ได้
              ขึ้น error เรื่องล็อกอิน/การเชื่อมต่อ การปิดหน้าต่าง agent (ไม่ใช่แค่ย่อ)
              จะทำให้การเชื่อมต่อหลุด
            </p>
          </div>
          <div>
            <p className="font-medium text-text">คำสั่งค้างที่ "Waiting for agent..." ตลอดไป</p>
            <p className="text-muted">
              เครื่องปลายทางน่าจะออฟไลน์ไปทันทีหลังส่งคำสั่ง ลองรีเฟรชหน้า Dashboard
              — เมื่อเชื่อมต่อกลับมาแล้ว ค่อยส่งคำสั่งใหม่อีกครั้ง
            </p>
          </div>
          <div>
            <p className="font-medium text-text">Windows บล็อกการดาวน์โหลด หรือขึ้นเตือน SmartScreen</p>
            <p className="text-muted">
              คลิก "More info" → "Run anyway" เหตุการณ์นี้เกิดขึ้นเพราะ agent ยังไม่ได้
              เซ็นด้วยใบรับรองแบบเสียเงิน (code-signing) ตัวไฟล์เองไม่มีการเปลี่ยนแปลง
              ระหว่างการดาวน์โหลดแต่ละครั้ง
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
