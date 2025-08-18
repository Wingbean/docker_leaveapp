// ----- ส่วน Dropdown เลือกเดือน -----

function getCurrentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function initMonthSelect() {
  const sel = document.getElementById("monthSelect");
  const now = new Date();
  const monthNamesThai = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
  ];

  sel.innerHTML = "";

  // เริ่มจาก ม.ค. ปีนี้ ไปถึง ธ.ค. ปีถัดไป (24 เดือน)
  for (let i = 0; i < 24; i++) {
    const date = new Date(now.getFullYear(), 0 + i, 1);  // เริ่มที่ ม.ค. ปีนี้
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const value = `${year}-${month}`;
    const label = `${monthNamesThai[date.getMonth()]} ${year}`;

    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;

    // ตั้ง default เป็นเดือนปัจจุบัน
    if (
      year === now.getFullYear() &&
      date.getMonth() === now.getMonth()
    ) {
      option.selected = true;
    }

    sel.appendChild(option);
  }

  sel.onchange = () => loadCalendar(sel.value);
}

// ----- ปฏิทินวันลา -----

async function loadCalendar(month = getCurrentMonth()) {
  const res = await axios.get(`/calendar?month=${month}`);
  const data = res.data;

  const dayMap = {}; // {'2025-06-01': ['คุณเอ (ลาพักร้อน)', ...]}

  data.forEach(row => {
    const start = new Date(row["Start Date"]);
    const end = new Date(row["End Date"]);
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const ymd = d.toISOString().split("T")[0];
      if (ymd.startsWith(month)) {
        if (!dayMap[ymd]) dayMap[ymd] = [];
        dayMap[ymd].push(`${row["Name"]} (${row["Leave Type"]})`);
      }
    }
  });

  const calendar = document.getElementById("calendar");
  calendar.innerHTML = "";

  const table = document.createElement("table");
  table.className = "table table-bordered table-striped align-middle";

  const header = document.createElement("tr");
  header.innerHTML = `
    <th>Date</th><th>Name(s)</th>
    <th>Date</th><th>Name(s)</th>
  `;
  table.appendChild(header);

  // --- START: ส่วนที่แก้ไข ---

  const daysInMonth = new Date(month.split("-")[0], month.split("-")[1], 0).getDate();
  // 1. คำนวณจำนวนแถวที่ต้องสร้าง (ปัดเศษขึ้น)
  //    - เดือนที่มี 30 วัน: Math.ceil(30 / 2) = 15 แถว
  //    - เดือนที่มี 31 วัน: Math.ceil(31 / 2) = 16 แถว
  const numberOfRows = Math.ceil(daysInMonth / 2);

  // 2. แก้ไข for loop ให้วนซ้ำตามจำนวนแถวที่คำนวณได้
  for (let i = 1; i <= numberOfRows; i++) {
    const leftDay = i;
    // 3. คำนวณวันที่ฝั่งขวาใหม่
    const rightDay = i + numberOfRows;

    const left = `${month}-${String(leftDay).padStart(2, "0")}`;
    const right = `${month}-${String(rightDay).padStart(2, "0")}`;

    const row = document.createElement("tr");
    if (i % 2 === 0) {
      row.className = "bg-white text-dark";
    } else {
      row.setAttribute("style", "background-color: #d3d3d3; color: #212529;");
    }

    // ตรวจสอบว่าวันที่ฝั่งขวาต้องแสดงหรือไม่ (ถ้าเกินจำนวนวันในเดือน ให้เป็นค่าว่าง)
    const rightDayCell = rightDay <= daysInMonth ? rightDay : "";
    const rightDataCell = rightDay <= daysInMonth ? (dayMap[right] || []).join("<br>") : "";

    row.innerHTML = `
      <td>${leftDay}</td>
      <td>${(dayMap[left] || []).join("<br>")}</td>
      <td>${rightDayCell}</td>
      <td>${rightDataCell}</td>
    `;
    table.appendChild(row);
  }
  // --- END: ส่วนที่แก้ไข ---

  calendar.appendChild(table);
}

// ----- ฟอร์มจองวันลา -----

document.getElementById("leaveForm").addEventListener("submit", async function (e) {
  e.preventDefault();

  const formData = new FormData(this);
  //const data = Object.fromEntries(formData.entries());
  try {
    const res = await axios.post("/submit", formData);
    alert(res.data.message || "บันทึกข้อมูลสำเร็จ");
    this.reset();
    loadCalendar();
    loadLeaveTable();
  } catch (err) {
    alert("เกิดข้อผิดพลาดในการส่งข้อมูล");
  }
});

// ----- ตารางรายการวันลาทั้งหมด -----

async function loadLeaveTable() {
  const res = await axios.get("/data");  // หรือ /leaves แล้วแต่ backend คุณ
  const data = res.data;

  const table = document.getElementById("leaveTable");
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");

  thead.innerHTML = "";
  tbody.innerHTML = "";

  if (data.length === 0) {
    tbody.innerHTML = "<tr><td colspan='7'>ไม่มีข้อมูลวันลา</td></tr>";
    return;
  }

  // ✅ 1. กำหนดหัวตาราง (ไม่เอา code มาโชว์)
  const headers = ["Timestamp", "Name", "Leave Type", "Start Date", "End Date", "Note"];
  const headerRow = document.createElement("tr");
  headers.forEach(h => {
    const th = document.createElement("th");
    th.textContent = h;
    headerRow.appendChild(th);
  });

  // ✅ เพิ่มหัวคอลัมน์ “ลบ”
  const deleteTh = document.createElement("th");
  deleteTh.textContent = "ลบ";
  headerRow.appendChild(deleteTh);
  thead.appendChild(headerRow);

  // ✅ 2. เติมข้อมูล
  data.forEach(row => {
    const tr = document.createElement("tr");

    headers.forEach(h => {
      const td = document.createElement("td");
      td.textContent = row[h];
      tr.appendChild(td);
    });

    // ✅ 3. ปุ่มลบ
    const deleteTd = document.createElement("td");
    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "ลบ";
    deleteBtn.className = "btn btn-danger btn-sm";
    deleteBtn.onclick = async () => {
      const code = prompt("กรอกรหัสลบเพื่อยืนยัน:");
      if (!code) return;

      try {
        const res = await axios.post("/delete", {
          timestamp: row["Timestamp"],
          code: code
        });

        if (res.data.success) {
          alert("ลบข้อมูลสำเร็จ");
          loadLeaveTable();  // รีโหลด
          loadCalendar();    // รีโหลดปฏิทินด้วย
        } else {
          alert("รหัสลบไม่ถูกต้อง กรุณาลองใหม่");
        }
      } catch (err) {
        alert("เกิดข้อผิดพลาดในการลบ");
      }
    };

    deleteTd.appendChild(deleteBtn);
    tr.appendChild(deleteTd);
    tbody.appendChild(tr);
  });
}

// Auto dismiss flash message after 3 seconds
setTimeout(() => {
  document.querySelectorAll('.alert').forEach(alert => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
    bsAlert.close();
  });
}, 3000);

// ----- โหลดตอนเปิดหน้า -----

initMonthSelect();
loadCalendar();
loadLeaveTable();
