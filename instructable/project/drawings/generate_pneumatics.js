const fs=require('fs'),path=require('path');
const sharp=require('/Users/scalarmac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const E=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;');
const T=(x,y,s,z=22,c='#263744',a='start')=>`<text x="${x}" y="${y}" font-size="${z}" fill="${c}" text-anchor="${a}">${E(s)}</text>`;
const R=(x,y,w,h,fill='#f4f7f9')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="5" fill="${fill}" stroke="#526b7a" stroke-width="2"/>`;
const W=(p,c='#296b8d',extra='')=>`<polyline points="${p}" fill="none" stroke="${c}" stroke-width="3" ${extra}/>`;
const P=(x,y)=>`<circle cx="${x}" cy="${y}" r="5" fill="white" stroke="#263744" stroke-width="2"/>`;
const B=(title,sub,w=2100,h=1400)=>`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><style>text{font-family:Arial,sans-serif}</style><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="context-stroke"/></marker></defs><rect width="${w}" height="${h}" fill="white"/>${T(55,55,title,32)}${T(55,96,sub,20)}${T(55,h-25,'REVIEW • functional port labels, not physical valve-port placement • © 2026 crackpotgumption • CC BY 4.0',17,'#687985')}`;
const FC=(x,y)=>R(x,y,90,45,'#fff0dc')+W(`${x+12},${y+33} ${x+78},${y+12}`,'#a36c2c','marker-end="url(#arrow)"');
function cylinder(x,y,w=185,h=220,position='neutral'){
 const fraction=position==='bottom'?.88:position==='top'?.12:.52;
 const pistonY=y+h*fraction;
 const rodEnd=position==='bottom'?y-12:position==='top'?y-115:y-50;
 return R(x,y,w,h,'#f0f6f9')+W(`${x+12},${pistonY} ${x+w-12},${pistonY}`,'#303840')+W(`${x+w/2},${pistonY} ${x+w/2},${rodEnd}`,'#303840')+P(x,y+40)+P(x+w,y+h-40);
}
let a=B('09 — Pneumatic supply and five target channels','One regulated compressor outlet feeds a six-connection manifold: one inlet and five branches.');
a+=R(60,140,500,145)+T(80,180,'FORTRESS compressor — item 64596',25)+T(80,220,'Existing outlet regulator: approximately 25 PSI',21)+T(80,254,'No separate in-cabinet regulator',20);
a+=W('560,210 940,210 940,340','#296b8d')+T(620,190,'¼-inch OD tubing',20);
a+=R(100,340,1880,85,'#e2eff5')+T(120,378,'SIX-CONNECTION MANIFOLD',24)+T(120,408,'1 inlet + 5 outlets',19)+P(940,340);
for(let i=0;i<5;i++){
 let x=130+i*370,mid=x+130;
 a+=P(mid,425)+W(`${mid},425 ${mid},620`,'#296b8d');
 a+=R(x,620,270,180,'#eef4f8')+T(x+15,653,`VALVE ${i}`,25)+T(x+15,685,'AIRIX 4V210-08, 12 V',20)+T(x+15,715,'5-way / 2-position',19);
 a+=P(mid,620)+T(mid+12,608,'SUPPLY',17);
 // Two work-port hoses use separate routes and actual cylinder-end symbols.
 a+=cylinder(x+45,920,185,220)+T(x+137,1190,`TARGET ${i} — MAL16×75`,20,'#263744','middle');
 a+=P(x+65,800)+P(x+210,800)+W(`${x+65},800 ${x+65},865 ${x+20},865 ${x+20},960 ${x+45},960`,'#397a45');
 a+=W(`${x+210},800 ${x+290},800 ${x+290},1100 ${x+230},1100`,'#705095');
 a+=T(x+20,902,'TOP',17,'#397a45')+T(x+250,1135,'BOTTOM',16,'#705095');
 // Two exhaust controls are grouped below the valve, not drawn in the work hoses.
 a+=P(x+45,740)+W(`${x+45},740 ${x-15},740 ${x-15},510 ${x+20},510`,'#a36c2c','stroke-dasharray="7 5"');
 a+=P(x+225,740)+W(`${x+225},740 ${x+300},740 ${x+300},510 ${x+260},510`,'#a36c2c','stroke-dasharray="7 5"');
 a+=FC(x+20,488)+FC(x+170,488)+T(x+135,475,'2 × BESL-01 exhaust controls',17,'#a36c2c','middle');
 a+=T(x+15,777,'WORK PORTS → cylinder ends',17);
}
a+=T(90,1260,'OFF: air to TOP retracts piston / lowers target. ON: air to BOTTOM extends piston / raises target.',23);
a+=T(90,1300,'Exhaust controls belong on the two valve exhaust ports. Each pair vents to atmosphere.',21);
a+='</svg>';

let b=B('10 — One channel: valve states and exhaust paths','Functional routing for each target. Identify connections by function rather than assuming the valve’s printed port letters.',1800,1250);
b+=R(70,170,1650,115)+T(95,207,'SUPPLY: regulated compressor → manifold → valve supply port',26)+T(95,253,'Quarter-inch OD tubing throughout; linked push fittings and cylinder-supplied fittings.',22);
function state(x,title,top,bottom,energized){let y=365;b+=R(x,y,720,625)+T(x+25,y+45,title,29);b+=R(x+30,y+110,300,180,'#e6f0f5')+T(x+48,y+145,'5/2 DIRECTIONAL VALVE',21)+T(x+48,y+185,'Supply → '+(energized?'BOTTOM':'TOP'),23)+T(x+48,y+225,(energized?'TOP':'BOTTOM')+' → exhaust',23);b+=cylinder(x+440,y+130,175,240,energized?'top':'bottom')+T(x+528,y+420,'DOUBLE-ACTING CYLINDER',19,'#263744','middle');b+=P(x+330,y+155)+P(x+330,y+245)+W(`${x+330},${y+155} ${x+400},${y+155} ${x+400},${y+170} ${x+440},${y+170}`,'#397a45')+W(`${x+330},${y+245} ${x+655},${y+245} ${x+655},${y+330} ${x+615},${y+330}`,'#705095');b+=T(x+415,y+110,'TOP PORT',19,'#397a45')+T(x+605,y+375,'BOTTOM PORT',18,'#705095','middle');b+=W(`${x+105},${y+290} ${x+105},${y+500}`,'#a36c2c')+W(`${x+255},${y+290} ${x+255},${y+500}`,'#a36c2c')+FC(x+60,y+460)+FC(x+210,y+460)+T(x+30,y+545,'BESL-01 controls on both exhaust ports',20,'#a36c2c')+T(x+30,y+580,'Exhaust vents to atmosphere',20);}
state(70,'OFF — coil de-energized',true,false,false);state(950,'ON — coil energized',false,true,true);
b+=T(90,1065,'Air to the BOTTOM port extends the piston and raises the target (ON).',25);
b+=T(90,1110,'Air to the TOP port retracts the piston and lowers the target (OFF); the opposite end exhausts.',23);
b+=T(90,1150,'The piston symbol shows the resulting lowered / raised position. Five channels; ten exhaust controls.',21);
b+='</svg>';
(async()=>{for(const[n,svg]of[['09_pneumatic_channels',a],['10_valve_states',b]]){fs.writeFileSync(path.join(__dirname,n+'.svg'),svg);await sharp(Buffer.from(svg)).png().toFile(path.join(__dirname,n+'.png'));}console.log('Created two pneumatic review drawings.');})();
