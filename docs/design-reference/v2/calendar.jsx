// Single calendar wireframe (1440x900) — week grid + day rail + milestone rail.
// We don't build a full grid view (gcal owns scheduling) — this view shows
// the WEEK as 7 day-columns of task cards, with the selected day's tasks
// expanded as a hero rail on the right. Milestone progress sits above.

function CalTopbar({ view = 'week' }) {
  return (
    <div className="topbar">
      <div className="logo"><span className="mark">S</span> scheduler</div>
      <div className="nav">
        <a>today</a>
        <a className="on">week</a>
        <a>milestones</a>
        <a>plan</a>
      </div>
      <div className="spacer" />
      <div className="sk-row">
        <div className="sk-box" style={{padding:'4px 10px', boxShadow:'none', borderWidth:1.5}}>
          <span className="sk-sub" style={{textTransform:'none', letterSpacing:0}}>
            <span style={{display:'inline-block', width:8, height:8, borderRadius:'50%', background:'#3b9d6e', marginRight:6, verticalAlign:'middle'}}></span>
            google calendar synced · 2m ago
          </span>
        </div>
        <span className="sk-btn tiny">⌘K</span>
        <div className="who"><div className="avatar">M</div></div>
      </div>
    </div>
  );
}

function MilestoneRail() {
  return (
    <div style={{padding:'14px 24px', borderBottom:'1.5px dashed var(--line-soft)', background:'var(--paper)', display:'flex', alignItems:'center', gap:18}}>
      <div>
        <div className="sk-sub">milestones · CS PhD applications</div>
        <div className="sk-row" style={{gap:6, marginTop:6}}>
          <span className="sk-chip on">SOP draft v1 ✓</span>
          <span className="sk-chip on">letter requests ✓</span>
          <span className="sk-chip coral">SOP v2 · 60%</span>
          <span className="sk-chip dashed">CV polish</span>
          <span className="sk-chip dashed">research statements</span>
          <span className="sk-chip dashed">submit · 5 schools</span>
        </div>
      </div>
      <div className="spacer" style={{flex:1}}></div>
      <div style={{textAlign:'right'}}>
        <div className="sk-sub">target</div>
        <div className="sk-h4">Dec 15, 2026 · ~32 wks</div>
      </div>
    </div>
  );
}

// Day column in the week grid
function DayCol({ day, num, count, today, selected, tasks }) {
  return (
    <div className="sk-box" style={{
      padding:'10px 10px', display:'flex', flexDirection:'column', gap:8, minHeight:0,
      background: selected ? 'rgba(255,90,60,0.05)' : (today ? 'rgba(255,216,77,0.18)' : '#fff'),
      borderColor: selected ? 'var(--accent)' : 'var(--ink)',
      borderWidth: selected ? 2.5 : 1.8,
      boxShadow: selected ? '3px 3px 0 var(--accent)' : (today ? '2px 2px 0 var(--ink)' : 'none')
    }}>
      <div className="sk-row" style={{justifyContent:'space-between', alignItems:'baseline'}}>
        <div className="sk-sub" style={{color: today?'var(--accent)':'var(--pencil)'}}>{day}</div>
        <div className="sk-h3" style={{color: selected?'var(--accent)':'var(--ink)'}}>{num}</div>
      </div>
      <div className="sk-sub lc" style={{color:'var(--pencil)', fontSize:11}}>{count}</div>
      <div style={{borderBottom:'1px dashed var(--line-soft)'}}></div>
      <div className="sk-col" style={{gap:5, minHeight:0}}>
        {tasks.map((t, i) => (
          <div key={i} style={{
            padding:'5px 7px',
            borderRadius:5,
            border: '1.5px solid var(--ink)',
            borderStyle: t.state==='proposed' ? 'dashed' : 'solid',
            background:
              t.state==='done'     ? 'var(--ink)'
            : t.state==='proposed' ? 'rgba(255,216,77,0.55)'
            : t.state==='task'     ? 'rgba(255,90,60,0.16)'
            : t.state==='rest'     ? 'var(--paper-2)' : '#fff',
            color: t.state==='done' ? 'var(--paper)' : 'var(--ink)'
          }}>
            {t.time && (
              <div className="sk-sub" style={{
                fontSize:10, color: t.state==='done'?'rgba(255,255,255,0.7)':undefined
              }}>{t.time}</div>
            )}
            <div style={{
              fontSize:12, fontWeight:700, lineHeight:1.2, marginTop:1,
              textDecoration: t.state==='done' ? 'line-through' : 'none'
            }}>{t.title}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

const WEEK = [
  {day:'MON', num:'27', count:'2 done', tasks:[
    {state:'done', time:'10a', title:'SOP outline'},
    {state:'done', time:'4p', title:'letter req · prof Lin'},
  ]},
  {day:'TUE', num:'28', count:'all done', tasks:[
    {state:'done', time:'9a', title:'lit review · 3 papers'},
    {state:'done', time:'2p', title:'CV draft v1'},
  ]},
  {day:'WED', num:'29', today:true, selected:true, count:'5 to go', tasks:[
    {state:'done', time:'9a', title:'AI/ML labs scan'},
    {state:'proposed', time:'10:30', title:'SOP v2 · intro'},
    {state:'task', time:'2p', title:'mtg · advisor Park'},
    {state:'task', time:'3:30', title:'fellowship app · NSF'},
    {state:'proposed', time:'5p', title:'reflect · 15m'},
  ]},
  {day:'THU', num:'30', count:'4 to go', tasks:[
    {state:'task', time:'9a', title:'SOP v2 · methods'},
    {state:'task', time:'11a', title:'school list refine'},
    {state:'proposed', time:'2p', title:'mock interview · prof'},
    {state:'proposed', time:'4p', title:'CV polish'},
  ]},
  {day:'FRI', num:'1', count:'milestone', tasks:[
    {state:'task', time:'10a', title:'SOP v2 final read'},
    {state:'proposed', time:'2p', title:'milestone check-in'},
  ]},
  {day:'SAT', num:'2', count:'rest', tasks:[
    {state:'rest', title:'rest day'}
  ]},
  {day:'SUN', num:'3', count:'planning', tasks:[
    {state:'task', time:'7p', title:'weekly check-in · 5m'},
  ]},
];

const DAY_RAIL = [
  { state:'done',     time:'9:00 — 9:30',   title:'AI/ML labs scan',
    meta:'30m planned · 28m actual · 6 leads logged' },
  { state:'proposed', time:'10:30 — 11:30', title:'SOP v2 · intro paragraph',
    meta:'proposed · 1h focus · no calendar conflicts',
    why:'lit review done · advisor mtg today gives fresh angle to weave in' },
  { state:'locked',   time:'12:00 — 13:00', title:'lunch w/ Sam',
    meta:'from your google calendar · cannot move' },
  { state:'task',     time:'14:00 — 14:45', title:'mtg · advisor Park',
    meta:'on calendar · brings draft + 3 questions',
    extras: ['recurring · weekly', 'video link in event'] },
  { state:'task',     time:'15:30 — 17:00', title:'fellowship app · NSF GRFP',
    meta:'on calendar · 1.5h' },
  { state:'proposed', time:'17:00 — 17:15', title:'reflect — what stuck?',
    meta:'proposed · 15m', why:'weekly cadence · drives drift detection' },
];

function DayRail() {
  return (
    <div className="sk-col" style={{gap:10, height:'100%', minHeight:0, overflow:'hidden'}}>
      <div className="sk-row" style={{justifyContent:'space-between', alignItems:'flex-end'}}>
        <div>
          <div className="sk-sub">selected · today</div>
          <h2 className="sk-h2">Wed, Apr 29</h2>
          <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:2}}>
            6 tasks · 1 done · 2 proposed · on track
          </div>
        </div>
        <div className="sk-row">
          <span className="sk-btn tiny yellow">accept 2 proposed</span>
        </div>
      </div>

      <div className="sk-col" style={{gap:8, overflow:'auto', paddingRight:6, paddingBottom:14, flex:1}}>
        {DAY_RAIL.map((t, i) => {
          const isProp = t.state === 'proposed';
          const isDone = t.state === 'done';
          const isLock = t.state === 'locked';
          return (
            <div key={i} className={'sk-box' + (isProp?' dashed':'') + (isDone?' fill-ink':'') + (isLock?' fill-paper2':'')}
                 style={{
                   padding:'12px 14px',
                   background:
                     isProp ? 'rgba(255,216,77,0.55)' :
                     isDone ? 'var(--ink)' :
                     isLock ? 'var(--paper-2)' :
                     t.state==='task' ? 'rgba(255,90,60,0.12)' : '#fff',
                   color: isDone ? 'var(--paper)' : 'var(--ink)',
                   opacity: isLock ? 0.78 : 1
                 }}>
              <div className="sk-row" style={{justifyContent:'space-between', alignItems:'flex-start', gap:10}}>
                <div style={{flex:1, minWidth:0}}>
                  <div className="sk-sub" style={{color: isDone?'rgba(255,255,255,0.7)':undefined}}>{t.time}</div>
                  <div className="sk-h4" style={{
                    marginTop:2,
                    color: isDone?'var(--paper)':'var(--ink)',
                    textDecoration: isDone ? 'line-through' : 'none'
                  }}>{t.title}</div>
                  <div className="sk-sub lc" style={{
                    color: isDone?'rgba(255,255,255,0.6)':'var(--pencil)', marginTop:3
                  }}>{t.meta}</div>
                  {t.why && (
                    <div className="sk-row" style={{gap:6, marginTop:6, alignItems:'flex-start'}}>
                      <span className="sk-sub" style={{color:'var(--accent)', fontSize:10}}>WHY</span>
                      <span style={{fontSize:13, color:'var(--ink-2)', lineHeight:1.4}}>{t.why}</span>
                    </div>
                  )}
                </div>
                <div className="sk-row" style={{gap:6, flexShrink:0}}>
                  {isProp && <><span className="sk-btn tiny ghost">edit</span><span className="sk-btn tiny coral">accept</span></>}
                  {t.state==='task' && <><span className="sk-btn tiny ghost">⋯</span><span className="sk-btn tiny primary">done</span></>}
                  {isDone && <span className="sk-sub" style={{color:'rgba(255,255,255,0.6)'}}>logged ✓</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CalendarMain() {
  return (
    <div className="app" style={{gridTemplateRows:'auto auto 1fr'}}>
      <CalTopbar />
      <MilestoneRail />

      <div style={{padding:'18px 24px', display:'grid', gridTemplateColumns:'1.55fr 1fr', gap:18, minHeight:0, overflow:'hidden'}}>
        {/* Week grid */}
        <div className="sk-col" style={{minHeight:0, overflow:'hidden'}}>
          <div className="sk-row" style={{justifyContent:'space-between'}}>
            <div className="sk-row">
              <span className="sk-btn tiny ghost">←</span>
              <h2 className="sk-h2">Apr 27 — May 3</h2>
              <span className="sk-btn tiny ghost">→</span>
              <span className="sk-btn tiny">today</span>
            </div>
            <div className="sk-sub">click a day to expand →</div>
          </div>

          <div style={{display:'grid', gridTemplateColumns:'repeat(7, 1fr)', gap:8, marginTop:14, flex:1, minHeight:0}}>
            {WEEK.map((d, i) => <DayCol key={i} {...d} />)}
          </div>

          {/* Footer legend */}
          <div className="sk-row" style={{gap:14, marginTop:12, paddingTop:10, borderTop:'1px dashed var(--line-soft)', flexWrap:'wrap'}}>
            <span className="sk-row" style={{gap:6}}>
              <span style={{width:14, height:14, border:'1.5px dashed var(--ink)', background:'rgba(255,216,77,0.55)', borderRadius:3}}></span>
              <span style={{fontSize:13}}>proposed</span>
            </span>
            <span className="sk-row" style={{gap:6}}>
              <span style={{width:14, height:14, border:'1.5px solid var(--ink)', background:'rgba(255,90,60,0.18)', borderRadius:3}}></span>
              <span style={{fontSize:13}}>accepted (on gcal)</span>
            </span>
            <span className="sk-row" style={{gap:6}}>
              <span style={{width:14, height:14, border:'1.5px solid var(--ink)', background:'var(--ink)', borderRadius:3}}></span>
              <span style={{fontSize:13}}>done</span>
            </span>
            <div className="spacer" style={{flex:1}}></div>
            <span className="sk-sub" style={{textTransform:'none', letterSpacing:0}}>
              <b style={{fontFamily:'var(--mono)', color:'var(--ink)'}}>↵</b> accept ·
              <b style={{fontFamily:'var(--mono)', color:'var(--ink)'}}>D</b> done ·
              <b style={{fontFamily:'var(--mono)', color:'var(--ink)'}}>R</b> resched
            </span>
          </div>
        </div>

        {/* Day rail */}
        <div style={{borderLeft:'1.5px dashed var(--line-soft)', paddingLeft:18, minHeight:0}}>
          <DayRail />
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CalendarMain, CalTopbar, MilestoneRail, WEEK, DayCol });
