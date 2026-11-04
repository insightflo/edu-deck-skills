"""edu-deck-solo 추가 아이콘(assets/icons/extra.svg) 생성기.

[파일 목적] 참고 덱 24종과 같은 선 아이콘 문법(viewBox 100, currentColor, 굵기 5, 둥근 끝)으로
  주제 일반용 아이콘을 만든다. 손으로 svg를 쓰면 속성 오타가 잦아서 표에서 생성한다.
[출력] <skill>/assets/icons/extra.svg
[수정시 주의] id는 references/icons.md 표와 짝이다. 참고 덱에서 옮긴 base.svg 의 id와 겹치면 빌드가 멈춘다.
"""
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets" / "icons" / "extra.svg"
# id: (선 그림, 채움 그림, 선 굵기)
ICONS = {
 "people": ('<circle cx="36" cy="34" r="13"/><path d="M10 84C10 62 62 62 62 84"/><circle cx="68" cy="30" r="11"/><path d="M62 52C78 50 92 60 92 80"/>', "", 5),
 "org": ('<rect x="38" y="10" width="24" height="18" rx="4"/><rect x="10" y="70" width="24" height="18" rx="4"/><rect x="38" y="70" width="24" height="18" rx="4"/><rect x="66" y="70" width="24" height="18" rx="4"/><path d="M50 28V70M22 70V50H78V70"/>', "", 5),
 "mail": ('<rect x="10" y="22" width="80" height="56" rx="8"/><path d="M14 28L50 54L86 28"/>', "", 5),
 "phone": ('<rect x="28" y="8" width="44" height="84" rx="9"/><path d="M44 20H56"/>', '<circle cx="50" cy="79" r="4"/>', 5),
 "chart": ('<path d="M12 12V86H90"/><rect x="26" y="54" width="12" height="22" rx="2"/><rect x="46" y="38" width="12" height="38" rx="2"/><rect x="66" y="22" width="12" height="54" rx="2"/>', "", 5),
 "trend": ('<path d="M10 78L36 52L54 66L88 30"/><path d="M66 30H88V52"/>', "", 6),
 "list": ('<path d="M38 28H86M38 50H86M38 72H86"/>', '<circle cx="19" cy="28" r="6"/><circle cx="19" cy="50" r="6"/><circle cx="19" cy="72" r="6"/>', 5),
 "clipboard": ('<rect x="18" y="16" width="64" height="76" rx="8"/><rect x="36" y="9" width="28" height="15" rx="4"/><path d="M32 46H68M32 60H68M32 74H54"/>', "", 5),
 "doc-check": ('<path d="M24 10H60L78 28V90H24Z"/><path d="M60 10V28H78"/><path d="M36 60L46 70L66 48"/>', "", 5),
 "stamp": ('<path d="M40 12H60V38C60 44 68 46 76 50C82 53 84 60 84 66H16C16 60 18 53 24 50C32 46 40 44 40 38Z"/><path d="M16 80H84"/>', "", 5),
 "signature": ('<path d="M10 72C20 48 28 38 34 42C40 46 30 68 38 68C46 68 50 50 56 52C62 54 58 66 64 66C70 66 74 58 82 56"/><path d="M10 86H90"/>', "", 5),
 "x": ('<circle cx="50" cy="50" r="38"/><path d="M36 36L64 64M64 36L36 64"/>', "", 7),
 "ban": ('<circle cx="50" cy="50" r="38"/><path d="M24 24L76 76"/>', "", 7),
 "warn": ('<path d="M50 12L90 84H10Z"/><path d="M50 38V58"/>', '<circle cx="50" cy="71" r="4.5"/>', 5),
 "info": ('<circle cx="50" cy="50" r="38"/><path d="M50 46V72"/>', '<circle cx="50" cy="32" r="4.5"/>', 5),
 "question": ('<circle cx="50" cy="50" r="38"/><path d="M39 40Q39 28 50 28Q61 28 61 38Q61 46 50 50V58"/>', '<circle cx="50" cy="70" r="4.5"/>', 5),
 "shield": ('<path d="M50 10L84 22V48C84 70 68 84 50 90C32 84 16 70 16 48V22Z"/><path d="M36 50L46 60L66 40"/>', "", 5),
 "lock": ('<rect x="20" y="44" width="60" height="44" rx="8"/><path d="M32 44V32C32 20 40 12 50 12C60 12 68 20 68 32V44M50 60V72"/>', "", 5),
 "key": ('<circle cx="30" cy="50" r="16"/><path d="M46 50H88M74 50V64M86 50V60"/>', "", 5),
 "eye": ('<path d="M8 50C20 30 34 22 50 22C66 22 80 30 92 50C80 70 66 78 50 78C34 78 20 70 8 50Z"/><circle cx="50" cy="50" r="13"/>', "", 5),
 "search": ('<circle cx="42" cy="42" r="26"/><path d="M62 62L86 86"/>', "", 6),
 "gear": ('<circle cx="50" cy="50" r="13"/><circle cx="50" cy="50" r="28"/><path d="M50 10V22M50 78V90M10 50H22M78 50H90M22 22L30 30M70 70L78 78M78 22L70 30M30 70L22 78"/>', "", 5),
 "tool": ('<path d="M60 12C48 10 38 22 42 34L14 62C10 66 10 72 14 76L24 86C28 90 34 90 38 86L66 58C78 62 90 52 88 40L76 52L64 48L60 36L72 24Z"/>', "", 5),
 "ladder": ('<path d="M30 10V90M70 10V90M30 26H70M30 44H70M30 62H70M30 80H70"/>', "", 5),
 "bulb": ('<path d="M36 66C28 58 22 50 22 38C22 22 34 10 50 10C66 10 78 22 78 38C78 50 72 58 64 66V74H36Z"/><path d="M38 84H62M42 92H58"/>', "", 5),
 "target": ('<circle cx="50" cy="50" r="38"/><circle cx="50" cy="50" r="23"/>', '<circle cx="50" cy="50" r="8"/>', 5),
 "flag": ('<path d="M22 90V12"/><path d="M22 16H78L66 34L78 52H22"/>', "", 5),
 "trophy": ('<path d="M30 14H70V36C70 50 62 60 50 60C38 60 30 50 30 36Z"/><path d="M30 22H16V30C16 40 22 46 30 46M70 22H84V30C84 40 78 46 70 46M50 60V76M34 88H66M38 88V80H62V88"/>', "", 5),
 "coin": ('<circle cx="50" cy="50" r="38"/><path d="M50 22V78M62 36Q58 30 50 30Q38 30 38 40Q38 48 50 50Q62 52 62 60Q62 70 50 70Q42 70 37 64"/>', "", 5),
 "money": ('<rect x="8" y="26" width="84" height="48" rx="6"/><circle cx="50" cy="50" r="12"/><path d="M20 40V60M80 40V60"/>', "", 5),
 "calc": ('<rect x="20" y="8" width="60" height="84" rx="9"/><rect x="30" y="18" width="40" height="18" rx="3"/>', '<rect x="29" y="46" width="10" height="9" rx="2"/><rect x="45" y="46" width="10" height="9" rx="2"/><rect x="61" y="46" width="10" height="9" rx="2"/><rect x="29" y="61" width="10" height="9" rx="2"/><rect x="45" y="61" width="10" height="9" rx="2"/><rect x="61" y="61" width="10" height="9" rx="2"/><rect x="29" y="76" width="10" height="9" rx="2"/><rect x="45" y="76" width="10" height="9" rx="2"/><rect x="61" y="76" width="10" height="9" rx="2"/>', 5),
 "home": ('<path d="M12 48L50 14L88 48"/><path d="M22 40V86H78V40"/><path d="M42 86V62H58V86"/>', "", 5),
 "factory": ('<path d="M10 88V46L32 58V46L54 58V46L74 58V18H88V88Z"/><path d="M24 74H34M44 74H54M64 74H74"/>', "", 5),
 "truck": ('<path d="M8 26H58V70H8Z"/><path d="M58 40H76L90 56V70H58"/><circle cx="26" cy="74" r="9"/><circle cx="72" cy="74" r="9"/>', "", 5),
 "car": ('<path d="M12 64V50L24 30H76L88 50V64Z"/><path d="M12 50H88"/><circle cx="30" cy="70" r="9"/><circle cx="70" cy="70" r="9"/>', "", 5),
 "globe": ('<circle cx="50" cy="50" r="38"/><ellipse cx="50" cy="50" rx="16" ry="38"/><path d="M12 50H88M18 30H82M18 70H82"/>', "", 4.5),
 "link": ('<path d="M42 58L58 42"/><path d="M46 30L54 22C62 14 74 14 80 20C86 26 86 38 78 46L70 54"/><path d="M54 70L46 78C38 86 26 86 20 80C14 74 14 62 22 54L30 46"/>', "", 6),
 "cloud": ('<path d="M28 76H74C84 76 92 68 92 58C92 48 84 40 74 40C72 28 62 20 50 20C38 20 28 28 26 40C16 42 8 50 8 58C8 68 16 76 28 76Z"/>', "", 5),
 "heart": ('<path d="M50 84C30 70 12 56 12 36C12 24 22 14 34 14C42 14 48 18 50 24C52 18 58 14 66 14C78 14 88 24 88 36C88 56 70 70 50 84Z"/>', "", 5),
 "star": ('<path d="M50 10L61 36L89 38L67 56L74 84L50 69L26 84L33 56L11 38L39 36Z"/>', "", 5),
 "leaf": ('<path d="M18 82C18 44 40 20 86 14C84 56 62 82 26 82"/><path d="M18 82L56 44"/>', "", 5),
 "hand": ('<path d="M34 56V24C34 20 37 18 40 18C43 18 46 20 46 24V48M46 22V16C46 12 49 10 52 10C55 10 58 12 58 16V48M58 22C58 18 61 16 64 16C67 16 70 18 70 22V50M70 32C70 28 73 26 76 26C79 26 82 28 82 32V60C82 78 70 90 54 90C42 90 34 84 28 74L16 54C14 50 16 46 20 45C24 44 27 46 30 50L34 56"/>', "", 5),
 "megaphone": ('<path d="M14 40V60H28L70 82V18L28 40Z"/><path d="M28 60L34 84H46L40 62"/><path d="M80 38C86 44 86 56 80 62"/>', "", 5),
 "bell": ('<path d="M24 70V46C24 30 36 18 50 18C64 18 76 30 76 46V70L84 78H16Z"/><path d="M42 86C44 90 47 92 50 92C53 92 56 90 58 86M50 10V18"/>', "", 5),
 "send": ('<path d="M10 46L90 12L68 88L48 58Z"/><path d="M48 58L90 12"/>', "", 5),
 "camera": ('<rect x="10" y="28" width="80" height="56" rx="9"/><path d="M34 28L40 16H60L66 28"/><circle cx="50" cy="56" r="15"/>', "", 5),
 "pin": ('<path d="M50 90C50 90 22 60 22 38C22 22 34 10 50 10C66 10 78 22 78 38C78 60 50 90 50 90Z"/><circle cx="50" cy="38" r="11"/>', "", 5),
 "pencil": ('<path d="M64 14L86 36L38 84L12 90L18 64Z"/><path d="M56 22L78 44M18 64L38 84"/>', "", 5),
 "refresh": ('<path d="M80 38C74 22 60 14 46 16C28 18 16 34 16 50"/><path d="M80 14V38H56"/><path d="M20 62C26 78 40 86 54 84C72 82 84 66 84 50"/><path d="M20 86V62H44"/>', "", 5),
 "scale": ('<path d="M50 16V86M30 86H70M22 28H78"/><path d="M22 28L12 54H32Z"/><path d="M78 28L68 54H88Z"/>', '<circle cx="50" cy="14" r="5"/>', 5),
 "hardhat": ('<path d="M16 66C16 42 30 26 50 26C70 26 84 42 84 66"/><path d="M8 66H92V76H8Z"/><path d="M42 26V46M58 26V46"/>', "", 5),
 "fire": ('<path d="M50 90C30 90 18 76 18 58C18 40 32 30 36 12C46 22 50 30 50 40C54 34 58 30 62 24C74 36 82 48 82 60C82 78 70 90 50 90Z"/><path d="M50 90C42 90 36 84 36 76C36 68 44 62 50 54C56 62 64 68 64 76C64 84 58 90 50 90Z"/>', "", 5),
 "medical": ('<rect x="12" y="12" width="76" height="76" rx="14"/><path d="M50 30V70M30 50H70"/>', "", 6),
 "thermo": ('<path d="M40 60V20C40 14 44 10 50 10C56 10 60 14 60 20V60C66 64 70 70 70 76C70 86 61 92 50 92C39 92 30 86 30 76C30 70 34 64 40 60Z"/><path d="M50 30V72"/>', '<circle cx="50" cy="76" r="8"/>', 5),
 "water": ('<path d="M50 10C50 10 22 44 22 62C22 78 34 90 50 90C66 90 78 78 78 62C78 44 50 10 50 10Z"/><path d="M36 64C36 72 42 78 50 78"/>', "", 5),
 "sun": ('<circle cx="50" cy="50" r="18"/><path d="M50 8V20M50 80V92M8 50H20M80 50H92M20 20L28 28M72 72L80 80M80 20L72 28M28 72L20 80"/>', "", 5),
 "trash": ('<path d="M16 26H84M40 26V16H60V26"/><path d="M24 26L28 88H72L76 26"/><path d="M42 42V74M58 42V74"/>', "", 5),
 "id-card": ('<rect x="8" y="20" width="84" height="60" rx="8"/><circle cx="32" cy="44" r="9"/><path d="M18 68C18 58 46 58 46 68M56 40H82M56 52H82M56 64H74"/>', "", 5),
 "graduation": ('<path d="M50 18L92 38L50 58L8 38Z"/><path d="M26 48V68C26 74 38 80 50 80C62 80 74 74 74 68V48M88 40V64"/>', "", 5),
 "stop": ('<path d="M34 10H66L90 34V66L66 90H34L10 66V34Z"/><path d="M32 50H68"/>', "", 6),
}

parts = []
for iid, (stroke, fill, sw) in ICONS.items():
    g = f'<g fill="none" stroke="currentColor" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{stroke}</g>'
    f = f'<g fill="currentColor">{fill}</g>' if fill else ""
    parts.append(f'<symbol id="i-{iid}" viewBox="0 0 100 100">{g}{f}</symbol>')
head = "<!-- edu-deck-solo 추가 아이콘 (tools/make_icons.py 로 생성). 같은 선 문법: viewBox 0 0 100 100, currentColor, 굵기 5 안팎 -->\n"
OUT.write_text(head + '<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden"><defs>\n' + "\n".join(parts) + "\n</defs></svg>\n", encoding="utf-8")
print(len(ICONS), "icons →", OUT)
