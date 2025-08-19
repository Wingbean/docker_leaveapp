// script.js (เวอร์ชันปรับปรุง) — ใส่คอมเมนต์ [CHANGE]/[WHY] ทุกจุดที่แก้
// จุดประสงค์: เร็วขึ้น, ปลอดภัยขึ้น (เลี่ยง XSS), เวลาแสดงผลถูกต้อง (UTC -> Asia/Bangkok), โค้ดอ่านง่าย/ทนทาน

// ================================
// Helpers: วันที่/เวลา และ DOM ปลอดภัย
// ================================

// [ADD] แปลงสตริง UTC ISO8601 (เช่น "2025-08-18T04:21:00Z") ให้เป็นเวลาไทยที่อ่านง่าย
// [WHY] ฝั่ง backend ตอนนี้ส่ง Timestamp เป็น UTC; ต้องแปลงแสดงผลเป็น Asia/Bangkok ให้ผู้ใช้
function fmtBkkFromUTC(isoUtcString) {
  try {
    const d = new Date(isoUtcString);
    return new Intl.DateTimeFormat("th-TH", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Bangkok",
    }).format(d);
  } catch {
    return isoUtcString || "";
  }
}

// [ADD] parse วันที่แบบ 'YYYY-MM-DD' อย่างปลอดภัย (ไม่ใช้ new Date('YYYY-MM-DD'))
// [WHY] new Date('YYYY-MM-DD') บางเบราว์เซอร์ตีความเป็น UTC แล้วขยับวันเพี้ยน; เราสร้าง Date(year, month-1, day) แทน
function parseYMD(ymd) {
  if (!ymd) return null;
  const [y, m, d] = String(ymd).split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

// [ADD] สร้าง <td> ที่ “ปลอดภัย” จากข้อความ (เลี่ยง innerHTML กับข้อมูลผู้ใช้)
// [WHY] ลดความเสี่ยง XSS เพราะเราใช้ textContent เสมอ
function td(text) {
  const el = document.createElement("td");
  el.textContent = text ?? "";
  return el;
}

// [ADD] เติมรายการชื่อ (หลายบรรทัด) แบบปลอดภัย โดยไม่ใช้ innerHTML รวมสตริง
function tdList(lines) {
  const el = document.createElement("td");
  (lines || []).forEach((s, i) => {
    const div = document.createElement("div");
    div.textContent = s;
    el.appendChild(div);
  });
  return el;
}

// ================================
// ส่วน Dropdown เลือกเดือน
// ================================

function getCurrentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function initMonthSelect() {
  const sel = document.getElementById("monthSelect");
  const now = new Date();
  const monthNamesThai = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
  ];

  sel.innerHTML = "";

  // เริ่มจาก ม.ค. ปีนี้ ไปถึง ธ.ค. ปีถัดไป (24 เดือน)
  for (let i = 0; i < 24; i++) {
    const date = new Date(now.getFullYear(), i, 1); // [CLEANUP] เดิมเขียน 0 + i
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const value = `${year}-${month}`;
    const label = `${monthNamesThai[date.getMonth()]} ${year}`;

    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;

    // ตั้ง default เป็นเดือนปัจจุบัน
    if (year === now.getFullYear() && date.getMonth() === now.getMonth()) {
      option.selected = true;
    }

    sel.appendChild(option);
  }

  sel.onchange = () => loadCalendar(sel.value);
}

// ================================
// ปฏิทินวันลา
// ================================

async function loadCalendar(month = getCurrentMonth()) {
  try {
    const res = await axios.get(`/calendar?month=${month}`);
    const data = res.data || [];

    // dayMap: {'2025-06-01': ['คุณเอ (ลาพักร้อน)', ...]}
    const dayMap = Object.create(null);

    // [CHANGE] ใช้ parseYMD เพื่อกันการเลื่อนวันเพราะ timezone
    data.forEach((row) => {
      const start = parseYMD(row["Start Date"]);
      const end = parseYMD(row["End Date"]);
      if (!start || !end) return;

      // เดินวันจาก start..end แบบ “วันที่” ไม่ยุ่ง timezone
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        const ymd = `${y}-${m}-${day}`;

        if (ymd.startsWith(month)) {
          if (!dayMap[ymd]) dayMap[ymd] = [];
          dayMap[ymd].push(`${row["Name"]} (${row["Leave Type"]})`);
        }
      }
    });

    const calendar = document.getElementById("calendar");
    calendar.innerHTML = "";

    // กำหนดตาราง
    const table = document.createElement("table");
    table.className = "table table-bordered align-middle calendar-table";

    // [FIX] ใส่ thead ให้เรียบร้อยก่อน
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    headRow.innerHTML = `<th>Date</th><th>Name(s)</th><th>Date</th><th>Name(s)</th>`;
    thead.appendChild(headRow);
    table.appendChild(thead);               // <-- [FIX] append thead ทันที

    // [FIX] ใช้ tbody จริง ๆ
    const tbody = document.createElement("tbody");

    // คำนวณจำนวนแถว
    const [Y, M] = month.split("-").map(Number);
    const daysInMonth = new Date(Y, M, 0).getDate();
    const numberOfRows = Math.ceil(daysInMonth / 2);

    for (let i = 1; i <= numberOfRows; i++) {
      const leftDay = i;
      const rightDay = i + numberOfRows;

      const leftKey = `${month}-${String(leftDay).padStart(2, "0")}`;
      const rightKey = `${month}-${String(rightDay).padStart(2, "0")}`;

      const row = document.createElement("tr");
      if (i % 2 === 1) row.classList.add("alt");   // zebra ที่ระดับ <tr>

      row.appendChild(td(String(leftDay)));
      row.appendChild(tdList(dayMap[leftKey] || []));

      if (rightDay <= daysInMonth) {
        row.appendChild(td(String(rightDay)));
        row.appendChild(tdList(dayMap[rightKey] || []));
      } else {
        row.appendChild(td(""));
        row.appendChild(td(""));
      }

      tbody.appendChild(row);                      // <-- [FIX] แปะเข้า tbody
    }

    // ประกอบตาราง
    table.appendChild(tbody);                      // <-- [FIX] ปิดท้ายด้วย tbody
    calendar.appendChild(table);


  } catch (err) {
    // [ADD] กันพังเวลา API ล่ม
    console.error("loadCalendar failed:", err);
    const calendar = document.getElementById("calendar");
    calendar.innerHTML = `<div class="alert alert-danger">โหลดปฏิทินไม่สำเร็จ</div>`;
  }
}

// ================================
// ฟอร์มจองวันลา
// ================================

document.getElementById("leaveForm").addEventListener("submit", async function (e) {
  e.preventDefault();

  // [ADD] กัน Double-submit
  const submitBtn = this.querySelector("button[type=submit]");
  if (submitBtn) submitBtn.disabled = true;

  const formData = new FormData(this);

  try {
    const res = await axios.post("/submit", formData);
    alert(res.data.message || "บันทึกข้อมูลสำเร็จ");
    this.reset();
    loadCalendar();
    loadLeaveTable();
  } catch (err) {
    // [CHANGE] แสดงรายละเอียดจาก backend ถ้ามี
    const msg = err?.response?.data?.message || "เกิดข้อผิดพลาดในการส่งข้อมูล";
    alert(msg);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
});

// ================================
// ตารางรายการวันลาทั้งหมด
// ================================

async function loadLeaveTable() {
  try {
    const res = await axios.get("/data");
    const data = res.data || [];

    const table = document.getElementById("leaveTable");
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");

    thead.innerHTML = "";
    tbody.innerHTML = "";

    if (data.length === 0) {
      tbody.innerHTML = "<tr><td colspan='7'>ไม่มีข้อมูลวันลา</td></tr>";
      return;
    }

    // [CLEANUP] หัวตาราง (ไม่โชว์ code)
    const headers = ["Timestamp", "Name", "Leave Type", "Start Date", "End Date", "Note"];
    const headerRow = document.createElement("tr");
    headers.forEach((h) => {
      const th = document.createElement("th");
      th.textContent = h;
      headerRow.appendChild(th);
    });
    const deleteTh = document.createElement("th");
    deleteTh.textContent = "ลบ";
    headerRow.appendChild(deleteTh);
    thead.appendChild(headerRow);

    // [CHANGE] เรนเดอร์ Timestamp เป็นเวลาไทย (UTC -> BKK) และใช้ textContent ทุกช่องเพื่อความปลอดภัย
    data.forEach((row) => {
      const tr = document.createElement("tr");

      headers.forEach((h) => {
        const tdEl = document.createElement("td");
        if (h === "Timestamp") {
          tdEl.textContent = fmtBkkFromUTC(row[h]); // [CHANGE] แปลงเวลาเป็นไทย
        } else {
          tdEl.textContent = row[h] ?? "";
        }
        tr.appendChild(tdEl);
      });

      // ปุ่มลบ
      const deleteTd = document.createElement("td");
      const deleteBtn = document.createElement("button");
      deleteBtn.textContent = "ลบ";
      deleteBtn.className = "btn btn-danger btn-sm";
      deleteBtn.onclick = async () => {
        const code = prompt("กรอกรหัสลบเพื่อยืนยัน:");
        // [CHANGE] ยอมให้ผู้ใช้กดยืนยันโดยไม่กรอก code (ตามฝั่ง backend ที่ให้ fallback ลบด้วย timestamp ได้)
        // ถ้าอยาก 'บังคับกรอก code เสมอ' ให้ยกเลิกตรงนี้เป็น: if (!code) return;
        try {
          const r = await axios.post("/delete", {
            timestamp: row["Timestamp"],
            code: code || "",
          });

          if (r.data && r.data.success) {
            alert("ลบข้อมูลสำเร็จ");
            loadLeaveTable();
            loadCalendar();
          } else {
            alert("ลบไม่สำเร็จ (รหัสไม่ตรงหรือหาแถวไม่เจอ)");
          }
        } catch (err) {
          alert("เกิดข้อผิดพลาดในการลบ");
        }
      };

      deleteTd.appendChild(deleteBtn);
      tr.appendChild(deleteTd);
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("loadLeaveTable failed:", err);
    const table = document.getElementById("leaveTable");
    const tbody = table.querySelector("tbody");
    if (tbody) {
      tbody.innerHTML = "<tr><td colspan='7'>โหลดข้อมูลไม่สำเร็จ</td></tr>";
    }
  }
}

// ================================
// Auto dismiss flash message
// ================================
setTimeout(() => {
  document.querySelectorAll(".alert").forEach((alert) => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
    bsAlert.close();
  });
}, 3000);

// ================================
// โหลดตอนเปิดหน้า
// ================================
initMonthSelect();
loadCalendar();
loadLeaveTable();
