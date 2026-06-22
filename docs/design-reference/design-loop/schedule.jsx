// Schedule review — hi-fi + INTERACTIVE (Loop)
// The screen that appears right after the agent proposes a week of blocks.
// A google-calendar-style time grid:
//   • PROPOSED blocks (clay, dashed) are draggable — snap to 15 min, move across days.
//   • IMPORTED google-calendar events are translucent and FIXED (cannot be dragged).
// Confirm writes the (adjusted) proposed blocks to Google Calendar.

const SC_START = 8;        // grid starts 8:00
const SC_END = 22;         // grid ends 22:00
const SC_HOURS = SC_END - SC_START;
const SC_HH = 52;          // px per hour (layout space)
const SC_SNAP = 15;        // minutes
const SC_DAYS = [
  {dow:'Mon', num:'27'}, {dow:'Tue', num:'28'}, {dow:'Wed', num:'29', today:true},
  {dow:'Thu', num:'30'}, {dow:'Fri', num:'1'}, {dow:'Sat', num:'2'}, {dow:'Sun', num:'3'},
];

// imported from Google Calendar — fixed, translucent
const SC_LOCKED = [
  {id:'l1', day:0, start:9*60, dur:75, title:'CS 161 lecture', where:'Soda 306'},
  {id:'l2', day:2, start:9*60, dur:75, title:'CS 161 lecture', where:'Soda 306'},
  {id:'l3', day:4, start:9*60, dur:75, title:'CS 161 lecture', where:'Soda 306'},
  {id:'l4', day:2, start:13*60, dur:180, title:'Café shift', where:'work'},
  {id:'l5', day:1, start:14*60, dur:60, title:'Recruiter call · Datadog', where:'phone'},
  {id:'l6', day:3, start:18*60, dur:60, title:'Gym', where:'RSF'},
  {id:'l7', day:5, start:19*60, dur:120, title:'Dinner w/ friends', where:'Berkeley'},
];

// proposed by the agent — draggable
const SC_PROPOSED_INIT = [
  {id:'p1', day:0, start:16*60,    dur:45, title:'Mock interview · peer'},
  {id:'p2', day:2, start:10*60+30, dur:60, title:'Graphs · Dijkstra drill'},
  {id:'p3', day:2, start:20*60,    dur:30, title:'Reflect — what stuck?'},
  {id:'p4', day:3, start:10*60,    dur:60, title:'System design · URL shortener'},
  {id:'p5', day:3, start:15*60,    dur:60, title:'DP · review wrong set'},
  {id:'p6', day:4, start:16*60,    dur:60, title:'Behavioral · 3 STAR stories'},
];

const scFmt = (min) => {
  let h = Math.floor(min/60), m = min%60;
  const ap = h >= 12 ? 'p' : 'a';
  let hh = h % 12; if (hh === 0) hh = 12;
  return m === 0 ? `${hh}${ap}` : `${hh}:${String(m).padStart(2,'0')}${ap}`;
};
const scOverlap = (a, b) => a.day === b.day && a.start < b.start + b.dur && b.start < a.start + a.dur;

function ScheduleReview() {
  const { ProductTopbar } = window;
  const [proposed, setProposed] = React.useState(SC_PROPOSED_INIT);
  const [dragId, setDragId] = React.useState(null);
  const [confirmed, setConfirmed] = React.useState(false);
  const colsRef = React.useRef(null);
  const geo = React.useRef(null);

  const yOf = (start) => (start - SC_START*60) / 60 * SC_HH;
  const hOf = (dur) => dur / 60 * SC_HH;

  const conflictsOf = (ev) => SC_LOCKED.some((l) => scOverlap(ev, l)) || proposed.some((p) => p.id !== ev.id && scOverlap(ev, p));

  const onDown = (e, ev) => {
    if (confirmed) return;
    e.preventDefault(); e.stopPropagation();
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch (_) {}
    const rect = colsRef.current.getBoundingClientRect();   // screen px (scale-aware)
    geo.current = {
      id: ev.id,
      dayW: rect.width / SC_DAYS.length,
      hourH: rect.height / SC_HOURS,
      x0: e.clientX, y0: e.clientY,
      origDay: ev.day, origStart: ev.start, dur: ev.dur,
    };
    setDragId(ev.id);
  };
  const onMove = (e, id) => {
    if (!geo.current || geo.current.id !== id) return;
    const g = geo.current;
    const dDay = Math.round((e.clientX - g.x0) / g.dayW);
    let dMin = Math.round((e.clientY - g.y0) / g.hourH * 60 / SC_SNAP) * SC_SNAP;
    const day = Math.max(0, Math.min(SC_DAYS.length - 1, g.origDay + dDay));
    const start = Math.max(SC_START*60, Math.min(SC_END*60 - g.dur, g.origStart + dMin));
    setProposed((arr) => arr.map((p) => p.id === id ? {...p, day, start} : p));
  };
  const onUp = (e) => {
    const g = geo.current;
    setDragId(null);
    geo.current = null;
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch (_) {}
    if (!g) return;
    // On drop: if the block overlaps ANY other task (imported gcal OR another
    // proposed block), snap it back to where the drag started.
    setProposed((arr) => {
      const me = arr.find((p) => p.id === g.id);
      if (!me) return arr;
      const hits = SC_LOCKED.some((l) => scOverlap(me, l)) || arr.some((p) => p.id !== me.id && scOverlap(me, p));
      if (!hits) return arr;
      return arr.map((p) => p.id === g.id ? { ...p, day: g.origDay, start: g.origStart } : p);
    });
  };

  const total = proposed.length;

  return (
    <div className="app" style={{gridTemplateRows:'auto auto 1fr'}}>
      <ProductTopbar nav="Week" />

      {/* proposal banner */}
      <div style={{
        padding:'14px 26px', borderBottom:'1px solid var(--line)',
        display:'flex', alignItems:'center', gap:18,
        background: confirmed ? 'var(--sage-soft)' : 'var(--clay-tint)'
      }}>
        <span className="agent-mark" style={{flex:'none'}}>{confirmed ? '✓' : '✦'}</span>
        <div style={{flex:1}}>
          {confirmed ? (
            <>
              <div className="t-h4">Added {total} blocks to Google Calendar</div>
              <div className="muted" style={{fontSize:13, marginTop:2}}>You can still drag or delete them on your calendar · <b style={{color:'var(--sage-deep)'}}>undo available for 60s</b></div>
            </>
          ) : (
            <>
              <div className="t-h4">The agent proposed {total} blocks for this week</div>
              <div className="muted" style={{fontSize:13, marginTop:2}}>Drag any <b style={{color:'var(--clay-deep)'}}>proposed</b> block to a new time or day. Your existing calendar events are fixed. Confirm when it looks right.</div>
            </>
          )}
        </div>
        {confirmed
          ? <button className="btn btn-soft" onClick={() => setConfirmed(false)}>Undo</button>
          : <div className="row" style={{gap:10}}>
              <button className="btn btn-ghost">Regenerate</button>
              <button className="btn btn-primary lg" onClick={() => setConfirmed(true)}>Confirm {total} → Google Calendar</button>
            </div>}
      </div>

      {/* calendar */}
      <div style={{display:'flex', flexDirection:'column', minHeight:0, overflow:'hidden'}}>
        {/* day header */}
        <div style={{display:'flex', borderBottom:'1px solid var(--line)', paddingRight:14}}>
          <div style={{width:56, flex:'none'}}></div>
          {SC_DAYS.map((d) => (
            <div key={d.dow} style={{flex:1, textAlign:'center', padding:'9px 0', display:'flex', flexDirection:'column', gap:2}}>
              <span className="label" style={{fontSize:11}}>{d.dow}</span>
              <span style={{
                fontFamily:'var(--serif)', fontSize:19, fontWeight:600,
                color: d.today ? '#fff' : 'var(--ink)',
                background: d.today ? 'var(--clay)' : 'transparent',
                width:30, height:30, lineHeight:'30px', borderRadius:'50%', margin:'0 auto'
              }}>{d.num}</span>
            </div>
          ))}
        </div>

        {/* scroll body */}
        <div style={{flex:1, overflow:'auto', minHeight:0}}>
          <div style={{display:'flex', position:'relative'}}>
            {/* hour gutter */}
            <div style={{width:56, flex:'none'}}>
              {Array.from({length:SC_HOURS}).map((_, i) => (
                <div key={i} style={{height:SC_HH, position:'relative'}}>
                  <span className="mono" style={{position:'absolute', top:-7, right:8, fontSize:11, color:'var(--muted-2)'}}>{scFmt((SC_START+i)*60)}</span>
                </div>
              ))}
            </div>

            {/* day columns + events */}
            <div ref={colsRef} style={{flex:1, display:'flex', position:'relative'}}>
              {/* horizontal hour lines */}
              {Array.from({length:SC_HOURS+1}).map((_, i) => (
                <div key={i} style={{position:'absolute', left:0, right:0, top:i*SC_HH, height:1, background:'var(--line)', pointerEvents:'none'}}></div>
              ))}
              {SC_DAYS.map((d, di) => (
                <div key={di} style={{
                  flex:1, position:'relative', borderLeft: di===0?'none':'1px solid var(--line)',
                  height:SC_HOURS*SC_HH,
                  background: d.today ? 'color-mix(in srgb, var(--clay-tint) 30%, transparent)' : 'transparent'
                }}>
                  {/* locked / imported gcal events — translucent, fixed */}
                  {SC_LOCKED.filter((l) => l.day === di).map((l) => (
                    <div key={l.id} title="From Google Calendar · fixed" style={{
                      position:'absolute', left:3, right:3, top:yOf(l.start), height:hOf(l.dur)-3,
                      background:'repeating-linear-gradient(135deg, rgba(108,120,134,0.16) 0 7px, rgba(108,120,134,0.08) 7px 14px)',
                      border:'1px solid rgba(108,120,134,0.34)', borderRadius:7,
                      padding:'5px 8px', overflow:'hidden', cursor:'not-allowed', opacity:0.92
                    }}>
                      <div style={{fontSize:11.5, fontWeight:600, color:'var(--muted)', display:'flex', alignItems:'center', gap:4}}>
                        <span style={{fontSize:10}}>🔒</span>{l.title}
                      </div>
                      <div className="mono" style={{fontSize:10, color:'var(--muted-2)', marginTop:1}}>{scFmt(l.start)}–{scFmt(l.start+l.dur)}</div>
                    </div>
                  ))}

                  {/* proposed events — draggable */}
                  {proposed.filter((p) => p.day === di).map((p) => {
                    const dragging = dragId === p.id;
                    const conflict = conflictsOf(p) && !confirmed;
                    return (
                      <div key={p.id}
                        onPointerDown={(e) => onDown(e, p)}
                        onPointerMove={(e) => onMove(e, p.id)}
                        onPointerUp={onUp}
                        style={{
                          position:'absolute', left:3, right:3, top:yOf(p.start), height:hOf(p.dur)-3,
                          background: confirmed ? '#fff' : 'var(--clay-tint)',
                          borderTop: confirmed ? '1px solid var(--clay)' : `1.5px ${dragging?'solid':'dashed'} ${conflict?'#c0492f':'var(--clay)'}`,
                          borderRight: confirmed ? '1px solid var(--clay)' : `1.5px ${dragging?'solid':'dashed'} ${conflict?'#c0492f':'var(--clay)'}`,
                          borderBottom: confirmed ? '1px solid var(--clay)' : `1.5px ${dragging?'solid':'dashed'} ${conflict?'#c0492f':'var(--clay)'}`,
                          borderLeft: `3px solid ${conflict?'#c0492f':'var(--clay-deep)'}`,
                          borderRadius:7, padding:'5px 8px', overflow:'hidden',
                          cursor: confirmed ? 'default' : (dragging ? 'grabbing' : 'grab'),
                          boxShadow: dragging ? '0 10px 26px -6px rgba(157,69,39,0.5)' : 'none',
                          zIndex: dragging ? 50 : 5, touchAction:'none', userSelect:'none',
                          transition: dragging ? 'none' : 'top .16s ease, box-shadow .12s'
                        }}>
                        <div style={{display:'flex', alignItems:'center', gap:5}}>
                          {!confirmed && <span style={{color:'var(--clay)', fontSize:10, letterSpacing:'-1px', flex:'none'}}>⠿</span>}
                          <span style={{fontSize:11.5, fontWeight:600, color:'var(--clay-deep)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{p.title}</span>
                        </div>
                        <div className="mono" style={{fontSize:10, color:'var(--clay-deep)', opacity:.8, marginTop:1}}>{scFmt(p.start)}–{scFmt(p.start+p.dur)}</div>
                        {conflict && hOf(p.dur) > 46 && <div style={{fontSize:9.5, color:'#c0492f', marginTop:2, fontWeight:600}}>⚠ overlaps a fixed event</div>}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* legend */}
        <div className="legend" style={{padding:'10px 26px', borderTop:'1px solid var(--line)'}}>
          <span className="lg"><span style={{width:13, height:13, borderRadius:3, border:'1.5px dashed var(--clay)', background:'var(--clay-tint)', display:'inline-block'}}></span>proposed · drag to adjust</span>
          <span className="lg"><span style={{width:13, height:13, borderRadius:3, border:'1px solid rgba(108,120,134,0.4)', background:'repeating-linear-gradient(135deg, rgba(108,120,134,0.2) 0 4px, rgba(108,120,134,0.07) 4px 8px)', display:'inline-block'}}></span>imported from Google Calendar · fixed</span>
          <span className="spacer"></span>
          <span className="muted" style={{fontSize:12}}>snaps to 15 min · drag across days</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ScheduleReview });
