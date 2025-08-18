// ฟอร์ม
document.getElementById("leaveForm").onsubmit = async function (e) {
  e.preventDefault();
  const formData = new FormData(e.target);
  await axios.post("/submit", formData);
  alert("ส่งข้อมูลสำเร็จ");
  e.target.reset();
  loadTable();
  loadCalendar();
};

// ตาราง
async function loadTable() {
  const res = await axios.get("/data");
  const table = document.getElementById("leaveTable");
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  if (res.data.length === 0) return;

  thead.innerHTML = "<tr>" + Object.keys(res.data[0]).map(k => `<th>${k}</th>`).join("") + "</tr>";
  tbody.innerHTML = res.data.map(row => `
    <tr>${Object.values(row).map(v => `<td>${v}</td>`).join("")}</tr>
  `).join("");
}

// ปฏิทิน
function getCurrentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

async function loadCalendar(month = getCurrentMonth()) {
  const res = await axios.get(`/calendar?month=${month}`);
  const data = res.data;

  const dayMap = {};  // { '2025-06-01': ['คุณเอ', 'คุณบี'], ... }

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

  // เตรียมข้อมูลแสดง
  const calendar = document.getElementById("calendar");
  calendar.innerHTML = "";

  const table = document.createElement("table");
  table.border = 1;
  table.style.width = "100%";

  const header = document.createElement("tr");
  header.innerHTML = "<th>Date</th><th>Name(s)</th><th>Date</th><th>Name(s)</th>";
  table.appendChild(header);

  const daysInMonth = new Date(month.split("-")[0], month.split("-")[1], 0).getDate();

  for (let i = 1; i <= 15; i++) {
    const leftDay = String(i).padStart(2, '0');
    const rightDay = String(i + 15).padStart(2, '0');
    const leftDate = `${month}-${leftDay}`;
    const rightDate = `${month}-${rightDay}`;

    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${i}</td>
      <td>${(dayMap[leftDate] || []).join(", ")}</td>
      <td>${i + 15 <= daysInMonth ? i + 15 : ""}</td>
      <td>${i + 15 <= daysInMonth ? (dayMap[rightDate] || []).join(", ") : ""}</td>
    `;
    table.appendChild(row);
  }

  calendar.appendChild(table);
}


// month select
function initMonthSelect() {
  const sel = document.getElementById("monthSelect");
  const now = new Date();

  const monthNamesThai = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
  ];

  for (let i = 0; i < 12; i++) {
    const monthValue = `${now.getFullYear()}-${String(i + 1).padStart(2, '0')}`;
    sel.innerHTML += `<option value="${monthValue}" ${i === now.getMonth() ? 'selected' : ''}>${monthNamesThai[i]}</option>`;
  }

  sel.onchange = () => loadCalendar(sel.value);
}


initMonthSelect();
loadTable();
loadCalendar();
