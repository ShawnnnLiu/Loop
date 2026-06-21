// Calendar — hi-fi (Loop · interview-prep & job-search scheduler)
// Google Calendar owns scheduling; we surface prep tasks & recruiting milestones.
// Week grid of day-columns + selected day expanded into a rail + milestone track.

function ProductTopbar({ nav = 'Week' }) {
  return (
    <div className="tb">
      <div className="brand">
        <span className="glyph">L</span>
        <span className="word">Loop</span>
      </div>
      <div className="tb-nav">
        <a>Today</a>
        <a className={nav === 'Week' ? 'on' : ''}>Week</a>
        <a className={nav === 'Milestones' ? 'on' : ''}>Pipeline</a>
        <a className={nav === 'Plan' ? 'on' : ''}>Plan</a>
      </div>
      <div className="spacer" />
      <div className="row" style={{gap:12}}>
        <span className="sync"><span className="dot"></span>Google Calendar synced · 2m ago</span>
        <span className="icon-btn">⌘K</span>
        <span className="avatar">M</span>
      </div>
    </div>
  );
}

const MILESTONES = [
  {label:'Résumé polished', state:'done'},
  {label:'12 apps sent', state:'done'},
  {label:'DSA core · 70%', state:'active'},
  {label:'System design ready', state:'todo'},
  {label:'Onsite loops', state:'todo'},
  {label:'Offer · decide', state:'todo'},
];

function MilestoneBar() {
  return (
    <div style={{padding:'14px 26px', borderBottom:'1px solid var(--line)', background:'color-mix(in srgb, var(--paper) 60%, #fff)', display:'flex', alignItems:'center', gap:20}}>
      <div>
        <div className="label" style={{marginBottom:9}}>Pipeline · New-grad backend search (Spring 2026)</div>
        <div className="ms-track">
          {MILESTONES.map((m, i) => (
            <React.Fragment key={m.label}>
              <span className={'ms ' + m.state}>
                <span className="tick">{m.state === 'done' ? '✓' : m.state === 'active' ? '◔' : ''}</span>
                {m.label}
              </span>
              {i < MILESTONES.length - 1 && <span className="ms-link"></span>}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div className="spacer" />
      <div style={{textAlign:'right'}}>
        <div className="label">Target</div>
        <div className="t-h4" style={{marginTop:4}}>May 4 · onsites · ~12 wks</div>
      </div>
    </div>
  );
}

const WK = [
  {dow:'Mon', num:'27', meta:'2 done', blocks:[
    {state:'done', t:'10a', n:'Graphs · BFS/DFS set'},
    {state:'done', t:'4p', n:'Apply · 3 infra startups'},
  ]},
  {dow:'Tue', num:'28', meta:'all done', blocks:[
    {state:'done', t:'9a', n:'DP · knapsack patterns'},
    {state:'done', t:'2p', n:'Recruiter call · Datadog'},
  ]},
  {dow:'Wed', num:'29', today:true, sel:true, meta:'5 to go', blocks:[
    {state:'done', t:'8:30a', n:'Warm-up · 2 easies'},
    {state:'proposed', t:'10a', n:'Graphs · Dijkstra drill'},
    {state:'locked', t:'1p', n:'Café shift'},
    {state:'accepted', t:'4:30', n:'Mock interview · peer'},
    {state:'proposed', t:'8p', n:'Reflect · 15m'},
  ]},
  {dow:'Thu', num:'30', meta:'4 to go', blocks:[
    {state:'accepted', t:'10a', n:'System design · URL shortener'},
    {state:'accepted', t:'1p', n:'Stripe OA · due Thu'},
    {state:'proposed', t:'3p', n:'DP · review wrong set'},
    {state:'proposed', t:'5p', n:'Behavioral · 3 STAR stories'},
  ]},
  {dow:'Fri', num:'1', meta:'milestone', blocks:[
    {state:'accepted', t:'11a', n:'Mock · system design'},
    {state:'proposed', t:'2p', n:'Milestone check-in'},
  ]},
  {dow:'Sat', num:'2', meta:'light', blocks:[
    {state:'accepted', t:'11a', n:'Contest · 1.5h'},
  ]},
  {dow:'Sun', num:'3', rest:true, meta:'rest', blocks:[
    {state:'rest', n:'Rest day'},
  ]},
];

function DayColumn({ d }) {
  return (
    <div className={'day' + (d.sel ? ' sel' : d.today ? ' today' : '') + (d.rest ? ' rest' : '')}>
      <div className="day-top">
        <span className="day-dow">{d.dow}</span>
        <span className="day-num">{d.num}</span>
      </div>
      <span className="day-meta">{d.meta}</span>
      <div className="divider" style={{borderColor:'var(--line)'}}></div>
      <div className="col" style={{gap:6}}>
        {d.blocks.map((b, i) => (
          b.state === 'rest'
            ? <div key={i} style={{fontSize:12.5, color:'var(--muted)', fontStyle:'italic', padding:'6px 2px'}}>{b.n}</div>
            : <div key={i} className={'blk ' + b.state}>
                {b.t && <div className="bt">{b.t}</div>}
                <div className="bn">{b.n}</div>
              </div>
        ))}
      </div>
    </div>
  );
}

const RAIL = [
  {state:'done', t:'8:30 – 9:00', n:'Warm-up · 2 easy problems', meta:'30m planned · 24m actual · 2 solved, both clean'},
  {state:'proposed', t:'10:00 – 11:00', n:'Graphs · Dijkstra drill', meta:'proposed · 1h focus · no calendar conflicts',
    why:'Graphs is your weakest topic and shows up in 2 of your target companies\' question banks — front-load it while fresh.'},
  {state:'locked', t:'13:00 – 16:00', n:'Café shift', meta:'from Google Calendar · your job · can\'t be moved'},
  {state:'accepted', t:'16:30 – 17:15', n:'Mock interview · peer', meta:'on calendar · 45m · medium graph + follow-up'},
  {state:'accepted', t:'17:30 – 18:00', n:'Log Stripe OA · due tomorrow', meta:'on calendar · don\'t miss the window'},
  {state:'proposed', t:'20:00 – 20:15', n:'Reflect — what stuck?', meta:'proposed · 15m',
    why:'Weekly cadence drives drift detection and next week\'s plan.'},
];

function DayRail() {
  return (
    <div className="col" style={{gap:13, height:'100%', minHeight:0}}>
      <div className="row" style={{justifyContent:'space-between', alignItems:'flex-end'}}>
        <div>
          <div className="label">Selected · today</div>
          <h2 className="t-h1" style={{marginTop:4}}>Wed, Apr 29</h2>
          <div className="muted" style={{fontSize:13, marginTop:3}}>6 tasks · 1 done · 2 proposed · <span style={{color:'var(--sage-deep)', fontWeight:600}}>on track</span></div>
        </div>
        <button className="btn btn-primary sm">Accept 2 proposed</button>
      </div>

      <div className="col" style={{gap:9, overflow:'auto', paddingRight:6, paddingBottom:8, flex:1, minHeight:0}}>
        {RAIL.map((r, i) => {
          const done = r.state === 'done', prop = r.state === 'proposed', lock = r.state === 'locked';
          return (
            <div key={i} className={'rail-item ' + r.state}>
              <div className="row" style={{justifyContent:'space-between', alignItems:'flex-start', gap:12}}>
                <div style={{flex:1, minWidth:0}}>
                  <div className="rail-time">{r.t}{lock && ' · 🔒'}</div>
                  <div className="rail-title">{r.n}</div>
                  <div className="rail-meta">{r.meta}</div>
                  {r.why && (
                    <div className="why">
                      <span className="wt">WHY</span>
                      <span className="wb">{r.why}</span>
                    </div>
                  )}
                </div>
                <div className="row" style={{gap:7, flexShrink:0}}>
                  {prop && <><button className="btn btn-soft sm">Edit</button><button className="btn btn-primary sm">Accept</button></>}
                  {r.state === 'accepted' && <button className="btn btn-ink sm">Mark done</button>}
                  {done && <span className="chip sage sm">logged ✓</span>}
                  {lock && <span className="chip sm">gcal</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CalendarScreen() {
  return (
    <div className="app" style={{gridTemplateRows:'auto auto 1fr'}}>
      <ProductTopbar nav="Week" />
      <MilestoneBar />
      <div style={{padding:'18px 26px', display:'grid', gridTemplateColumns:'1.62fr 1fr', gap:24, minHeight:0, overflow:'hidden'}}>
        {/* week */}
        <div className="col" style={{minHeight:0, gap:14}}>
          <div className="row" style={{justifyContent:'space-between'}}>
            <div className="row" style={{gap:10}}>
              <span className="icon-btn">←</span>
              <h2 className="t-h2">Apr 27 — May 3</h2>
              <span className="icon-btn">→</span>
              <button className="btn btn-soft sm">Today</button>
            </div>
            <span className="muted" style={{fontSize:12.5}}>click a day to expand →</span>
          </div>

          <div className="cal-grid" style={{flex:1}}>
            {WK.map((d, i) => <DayColumn key={i} d={d} />)}
          </div>

          <div className="divider"></div>
          <div className="legend">
            <span className="lg"><span className="sw proposed"></span>proposed</span>
            <span className="lg"><span className="sw accepted"></span>accepted (on gcal)</span>
            <span className="lg"><span className="sw done"></span>done</span>
            <span className="spacer"></span>
            <span className="muted" style={{fontSize:12, display:'flex', gap:8, alignItems:'center'}}>
              <span className="kbd">↵</span> accept <span className="kbd">D</span> done <span className="kbd">R</span> reschedule
            </span>
          </div>
        </div>

        {/* rail */}
        <div style={{borderLeft:'1px solid var(--line)', paddingLeft:24, minHeight:0}}>
          <DayRail />
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CalendarScreen, ProductTopbar, MilestoneBar, WK, DayColumn });
