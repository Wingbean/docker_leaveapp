import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

fonts = [
    "Garuda", "Loma", "Sawasdee", "Tlwg Typist", "Tlwg Typo",
    "Waree", "Purisa", "Umpush", "Kinnari", "Norasi", "Laksaman"
]

plt.figure(figsize=(8, len(fonts) * 1.2))
for i, font in enumerate(fonts):
    plt.text(0.01, 1 - i*0.08, f"{font}: สวัสดีครับ ฟอนต์นี้คือ {font}", fontsize=16, fontname=font)

plt.axis('off')
plt.tight_layout()
plt.savefig("thai_fonts_preview.png", dpi=150)