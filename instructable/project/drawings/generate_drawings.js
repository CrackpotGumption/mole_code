// Editable SVG review drawings. Dimensions are inches; not full-size templates.
const fs = require('fs');
const path = require('path');
const sharp = require('/Users/scalarmac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out = __dirname;
const esc = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const text = (x,y,s,size=20,fill='#243342',anchor='start') => `<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" text-anchor="${anchor}">${esc(s)}</text>`;
const rect=(x,y,w,h,fill='#eaf2f7',stroke='#38566d',extra='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" stroke="${stroke}" stroke-width="2" ${extra}/>`;
const line=(x1,y1,x2,y2,color='#38566d',extra='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="2" ${extra}/>`;
const begin=(title,sub)=>`<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1200" viewBox="0 0 1600 1200"><style>text{font-family:Arial,sans-serif} .dim{marker-start:url(#arrow);marker-end:url(#arrow)}</style><defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#38566d"/></marker></defs><rect width="1600" height="1200" fill="white"/>${text(60,65,title,34)}${text(60,105,sub,19)}${text(60,1170,'REVIEW DRAWING • 2026-10-14 • dimensions in inches • ¾-inch plywood • not a full-size drilling template',17,'#697681')}`;
const dimH=(x,y,w,label)=>line(x,y,x+w,y,'#38566d','class="dim"')+text(x+w/2,y-10,label,19,'#243342','middle');
const dimV=(x,y,h,label)=>line(x,y,x,y+h,'#38566d','class="dim"')+text(x-12,y+h/2,label,19,'#243342','end');

let a=begin('01 — Plywood cuts and two-sheet layout','Proposed cutting sequence from confirmed panel dimensions. Sheet layouts include a ⅛-inch kerf between row blanks.');
const rows=[['Sides','2','24 deep × 36 high'],['Top / playfield','1','36 wide × 24 deep'],['Bottom','1','36 wide × 23.25 deep'],['Front','1','36 wide × 35.25 high'],['Deck panels','2','35.75 wide × 19.2 deep']];
a+=text(60,160,'CUT LIST — seven panels',24);
rows.forEach((r,i)=>{let y=205+i*44;a+=text(60,y,r[0],22)+text(285,y,'× '+r[1],22)+text(365,y,r[2],22);});
a+=text(60,470,'Cut full-width row blanks first; then rip each blank to its panel width.',19);
a+=text(60,505,'Two sheets are required by panel area. This layout leaves trimming allowance.',19);
function sheet(x,parts,title){let y=610,s=4.8,inner='';inner+=text(x,y-45,title,24);inner+=rect(x,y,48*s,96*s,'#f6f7f8','#647786');let offset=0;parts.forEach(p=>{let yy=y+offset*s;inner+=rect(x,yy,p.w*s,p.h*s,'#deedf3');inner+=text(x+p.w*s/2,yy+p.h*s/2-5,p.name,16,'#243342','middle')+text(x+p.w*s/2,yy+p.h*s/2+18,`${p.w} × ${p.h}`,15,'#243342','middle');offset+=p.h+.125;});inner+=dimH(x,y-15,48*s,'48')+dimV(x-22,y,96*s,'96');return inner;}
a+=sheet(130,[{name:'Side 1',w:36,h:24},{name:'Side 2',w:36,h:24},{name:'Front',w:36,h:35.25}],'Sheet A');
a+=sheet(520,[{name:'Top',w:36,h:24},{name:'Bottom',w:36,h:23.25},{name:'Deck top',w:35.75,h:19.2},{name:'Deck bottom',w:35.75,h:19.2}],'Sheet B');
a+=text(900,655,'ROW LENGTHS INCLUDING KERFS',21);
a+=text(900,700,'Sheet A: 83.50 of 96',21)+text(900,738,'Sheet B: 86.025 of 96',21);
a+=text(900,800,'Blank areas are offcuts, not additional parts.',18);
a+=text(900,838,'Allow for edge cleanup and actual blade kerf.',18);
a+=text(900,876,'Keep the bottom deck panel solid.',18);
a+='</svg>';

let b=begin('02 — Playfield and deck hole layouts','View from above. Each panel has its OWN front-left origin. Coordinates are (left-to-right, front-to-back).');
function panel(x,y,w,d,diam,pts,title){let s=17,body=text(x,y-68,title,25)+dimH(x,y-27,w*s,`${w} wide`)+rect(x,y,w*s,d*s);body+=dimV(x-28,y,d*s,`${d} deep`);pts.forEach((p,i)=>{let cx=x+p[0]*s,cy=y+(d-p[1])*s;body+=`<circle cx="${cx}" cy="${cy}" r="${diam*s/2}" fill="white" stroke="#337b91" stroke-width="2"/>`+line(cx-8,cy,cx+8,cy,'#337b91')+line(cx,cy-8,cx,cy+8,'#337b91')+text(cx,cy-12,`Target ${i}`,17,'#243342','middle')+text(cx,cy+24,`(${p[0]}, ${p[1]})`,16,'#243342','middle');});body+=`<circle cx="${x}" cy="${y+d*s}" r="5" fill="#b85130"/>`+text(x,y+d*s+30,'(0, 0) FRONT-LEFT',18,'#b85130')+text(x+w*s/2,y-7,'BACK',16,'#697681','middle')+text(x+w*s/2,y+d*s+30,'FRONT',18,'#243342','middle');return body;}
const play=[[6,6],[18,6],[30,6],[12,18],[24,18]],deck=[[6,3.75],[18,3.75],[30,3.75],[12,15.75],[24,15.75]];
b+=panel(150,265,36,24,8.5,play,'TOP / PLAYFIELD — 36 × 24');
b+=panel(890,265,35.75,19.2,4.25,deck,'UPPER DECK — 35.75 × 19.2');
b+=text(110,790,'Playfield: five Ø8.5 cut openings.',23)+text(890,790,'Deck: five approximately Ø4.25 openings.',23);
b+=text(110,830,'Printed collars reduce the clear aperture.',18)+text(890,830,'Check fit against Oatey 435032 before batch cutting.',18);
b+=text(110,910,'PLACEMENT: center the pneumatic deck between the cabinet rails.',24);
b+=text(110,952,'The different depth coordinates account for the different front-left origins.',21);
b+=text(110,990,'Do not add a separate rearward placement offset. Use the recorded coordinates for each panel.',21);
b+=text(110,1050,'Review detail: deck width is ¼ inch less than the playfield width; both recorded X layouts are unchanged.',18,'#8b4c22');
b+=text(110,1082,'This drawing does not invent a horizontal centering correction for the hole coordinates.',18,'#8b4c22');
b+='</svg>';

let c=begin('03 — Bottom setback and panel relationship','Side section schematic, viewed from the cabinet side. Front is left; rear is right. Framing and trim omitted.');
let x=270,y=265,s=22;
c+=rect(x,y,24*s,36*s,'#f8fafb','#bcc7ce');
c+=rect(x,y,24*s,.75*s,'#c6dce7');
c+=rect(x,y+.75*s,.75*s,35.25*s,'#efcfad','#a97341');
c+=rect(x+.75*s,y+35.25*s,23.25*s,.75*s,'#c6dce7');
c+=dimH(x,y-35,24*s,'24 overall side depth');
c+=dimV(x-45,y,36*s,'36 side height');
c+=dimH(x+.75*s,y+36*s+40,23.25*s,'23.25 bottom depth');
c+=text(900,325,'TOP: 36 wide × 24 deep × ¾ thick',23);
c+=text(900,375,'FRONT: 36 wide × 35.25 tall × ¾ thick',23);
c+=text(900,425,'BOTTOM: 36 wide × 23.25 deep × ¾ thick',23);
c+=text(900,510,'The front drops below the top panel',22)+text(900,545,'to align with the side-panel bottoms.',22);
c+=text(900,615,'The bottom starts ¾ inch back from',22)+text(900,650,'the front edge, allowing the front panel',22)+text(900,685,'to occupy that space.',22);
c+=text(900,770,'Front and bottom share a bottom datum.',21);
c+=text(900,815,'Schematic confirms the supplied panel',19)+text(900,845,'dimensions; joint details are for review.',19);
c+=text(900,930,'Outside width: 37.5',23)+text(900,970,'36-inch panels between two ¾-inch sides.',19);
c+='</svg>';

(async()=>{for(const [name,svg] of [['01_plywood_cuts',a],['02_hole_layouts',b],['03_front_bottom_setback',c]]){fs.writeFileSync(path.join(out,name+'.svg'),svg);await sharp(Buffer.from(svg)).png().toFile(path.join(out,name+'.png'));}console.log('Created three SVG drawings and three PNG review images.');})();
