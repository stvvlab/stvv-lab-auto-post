from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
W,H=1600,900
im=Image.new("RGB",(W,H),"#071a32");d=ImageDraw.Draw(im)
d.rectangle((0,0,W,15),fill="#ffdc13")
d.rectangle((0,0,30,H),fill="#ffdc13")
d.rectangle((50,55,1550,130),fill="#102b4a")
d.rectangle((50,190,1550,345),fill="#ffdc13")
d.rectangle((50,380,1550,510),fill="#122d4e")
for x in (50,550,1050): d.rectangle((x,560,x+465,715),outline="#ffdc13",width=5)
font="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
def write(x,y,t,size,color): d.text((x,y),t,font=ImageFont.truetype(font,size),fill=color)
write(80,63,"STVV LAB  /  MATCH RESULT",50,"#ffffff")
write(85,208,"STVV  4 - 1  ZULTE WAREGEM",80,"#071a32")
write(80,402,"日本人3選手がゴール！",77,"#ffffff")
write(70,582,"新川志音",53,"#ffffff");write(70,650,"7分",35,"#ffdc13")
write(570,582,"石渡ネルソン",46,"#ffffff");write(570,650,"12分",35,"#ffdc13")
write(1070,582,"松澤海斗",53,"#ffffff");write(1070,650,"66分",35,"#ffdc13")
write(70,770,"セヴァウィ  64分（PK）  |  2026.11.09 JST",37,"#ffdc13")
write(70,840,"BELGIAN LEAGUE  ROUND 11",25,"#ffffff")
Path("generated").mkdir(exist_ok=True)
im.save("generated/2026-11-09_zulte_4_1_japanese_three.png",optimize=True)
