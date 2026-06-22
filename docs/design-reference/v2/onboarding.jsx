// Onboarding · deterministic wizard with one LLM-powered step (resume / file parse).
// Three layout variants — all share the same "deterministic for easy stuff,
// LLM only when reading user-supplied files" model.

function OBChrome({ step, total = 7, children }) {
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <div className="topbar">
        <div className="logo"><span className="mark">S</span> scheduler</div>
        <div className="spacer" />
        <div className="sk-sub">setup · step {step} of {total}</div>
        <div style={{display:'flex', gap:5, marginLeft:14}}>
          {Array.from({length: total}).map((_, i) => (
            <div key={i} style={{
              width: 28, height: 7, borderRadius: 4,
              background: (i+1) <= step ? 'var(--accent)' : 'rgba(0,0,0,0.15)'
            }} />
          ))}
        </div>
        <div className="sk-btn ghost tiny" style={{marginLeft:14}}>save &amp; exit</div>
      </div>
      {children}
    </div>
  );
}

function StepBadge({ kind }) {
  const isLLM = kind === 'llm';
  return (
    <div className="sk-row" style={{
      gap:6, padding:'4px 10px', borderRadius:999,
      border:'1.5px solid var(--ink)',
      background: isLLM ? 'var(--accent)' : '#fff',
      color: isLLM ? '#fff' : 'var(--ink)',
      width:'fit-content', fontFamily:'var(--mono)', fontSize:11, letterSpacing:'0.04em', textTransform:'uppercase'
    }}>
      <span style={{
        width:14, height:14, borderRadius:3, border:'1.5px solid '+(isLLM?'#fff':'var(--ink)'),
        background: isLLM ? '#fff' : 'transparent', color: isLLM ? 'var(--accent)' : 'var(--ink)',
        display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:10, lineHeight:1
      }}>{isLLM ? 'L' : 'D'}</span>
      {isLLM ? 'LLM-assisted' : 'deterministic'}
    </div>
  );
}

// ────────── A · stepped wizard, deterministic step (deadline) ──────────
function OnboardingA() {
  return (
    <OBChrome step={3}>
      <div style={{padding:'48px 80px', display:'grid', gridTemplateColumns:'80px 1fr 320px', gap:32, alignItems:'start'}}>
        {/* step list rail */}
        <div className="sk-col" style={{gap:8, fontSize:12}}>
          {['goal','hours','deadline','skills','resume','accountability','calendar'].map((s,i) => (
            <div key={s} className="sk-row" style={{gap:8, opacity: i+1===3?1:0.45}}>
              <div style={{width:20, height:20, borderRadius:'50%', border:'1.5px solid var(--ink)',
                background: i+1 < 3 ? 'var(--ink)' : i+1 === 3 ? 'var(--accent)' : '#fff',
                color: i+1 <= 3 ? '#fff' : 'var(--ink)',
                display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:11
              }}>{i+1 < 3 ? '✓' : i+1}</div>
              <span style={{fontFamily:'var(--mono)', fontSize:11, textTransform:'uppercase', letterSpacing:'0.04em'}}>{s}</span>
            </div>
          ))}
        </div>

        {/* main */}
        <div className="sk-col" style={{gap:14, maxWidth:560}}>
          <StepBadge kind="det" />
          <h1 className="sk-h1">when's your deadline?</h1>
          <div className="sk-sub lc" style={{color:'var(--pencil)'}}>
            we back-plan from this date. simple form — no AI guessing. you can edit later.
          </div>

          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginTop:10}}>
            <div className="sk-box"><div className="sk-sub">soon</div><div className="sk-h3">in 4 weeks</div></div>
            <div className="sk-box thick fill-coral"><div className="sk-sub">selected</div><div className="sk-h3">in 12 weeks</div></div>
            <div className="sk-box"><div className="sk-sub">long runway</div><div className="sk-h3">in 6 months</div></div>
            <div className="sk-box dashed"><div className="sk-sub">custom</div><div className="sk-h3">pick a date →</div></div>
          </div>

          <div className="sk-box fill-paper2" style={{marginTop:6, padding:'14px 18px'}}>
            <div className="sk-row" style={{justifyContent:'space-between'}}>
              <div><div className="sk-sub">target date</div><div className="sk-h3">February 14, 2026</div></div>
              <div style={{textAlign:'right'}}><div className="sk-sub">runway</div><div className="sk-h3" style={{color:'var(--accent)'}}>~ 12 weeks</div></div>
            </div>
          </div>

          <div className="sk-row" style={{justifyContent:'space-between', marginTop:14}}>
            <span className="sk-btn ghost">← back</span>
            <span className="sk-btn primary lg">next: skills →</span>
          </div>
          <div className="sk-sub" style={{textAlign:'center', marginTop:4, color:'var(--pencil-soft)'}}>
            press <b style={{fontFamily:'var(--mono)', color:'var(--ink)'}}>↵</b> to continue
          </div>
        </div>

        {/* trust panel */}
        <div className="sk-box dashed" style={{padding:'14px 16px', background:'rgba(255,255,255,0.7)'}}>
          <div className="sk-sub">why a wizard?</div>
          <div className="sk-h4" style={{marginTop:4}}>deterministic where we can be</div>
          <div className="sk-sub lc" style={{marginTop:8, color:'var(--pencil)'}}>
            simple questions don't need an LLM. plain forms = faster, predictable, no hallucinated answers.
          </div>
          <div className="sk-sub" style={{marginTop:14}}>LLM only when:</div>
          <div className="sk-col" style={{gap:5, marginTop:6}}>
            <div className="sk-chip coral" style={{fontSize:12, alignSelf:'flex-start'}}>parsing your resume</div>
            <div className="sk-chip coral" style={{fontSize:12, alignSelf:'flex-start'}}>reading uploaded files</div>
            <div className="sk-chip coral" style={{fontSize:12, alignSelf:'flex-start'}}>drafting the syllabus</div>
          </div>
        </div>
      </div>

      <div style={{padding:'14px 80px', borderTop:'1.5px dashed var(--line-soft)', display:'flex', justifyContent:'space-between', background:'var(--paper)'}}>
        <div className="sk-sub">3 of 7 · est. 2 min remaining</div>
        <div className="sk-sub">all answers are editable later in <b style={{fontFamily:'var(--mono)', color:'var(--ink)'}}>settings</b></div>
      </div>
    </OBChrome>
  );
}

// ────────── B · LLM step: resume upload & parse ──────────
function OnboardingB() {
  return (
    <OBChrome step={5}>
      <div style={{padding:'48px 80px', display:'grid', gridTemplateColumns:'1fr 1fr', gap:36, alignItems:'start'}}>
        {/* upload side */}
        <div className="sk-col" style={{gap:14}}>
          <StepBadge kind="llm" />
          <h1 className="sk-h1">drop your resume</h1>
          <div className="sk-sub lc" style={{color:'var(--pencil)'}}>
            this is the one place we use an LLM during setup. it reads your resume so you don't have to retype your stack &amp; experience.
          </div>

          <div className="sk-box dashed" style={{padding:32, textAlign:'center', borderWidth:2.5, marginTop:6}}>
            <div style={{fontFamily:'var(--hand-title)', fontSize:42, lineHeight:1, color:'var(--accent)'}}>↧</div>
            <div className="sk-h3" style={{marginTop:8}}>drop your resume here</div>
            <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:6}}>
              .pdf, .docx, .txt · stays on our servers, never shared
            </div>
            <div className="sk-row" style={{justifyContent:'center', gap:8, marginTop:16}}>
              <span className="sk-btn">browse files</span>
              <span className="sk-btn ghost">paste linkedin url</span>
              <span className="sk-btn ghost">skip →</span>
            </div>
          </div>

          <div className="sk-box fill-paper2" style={{padding:'12px 14px'}}>
            <div className="sk-sub">just uploaded</div>
            <div className="sk-row" style={{justifyContent:'space-between', marginTop:6}}>
              <div className="sk-row" style={{gap:10}}>
                <div style={{width:36, height:44, border:'1.5px solid var(--ink)', borderRadius:4, background:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--mono)', fontSize:10}}>PDF</div>
                <div>
                  <div className="sk-h4">maya_chen_resume.pdf</div>
                  <div className="sk-sub lc" style={{color:'var(--pencil)'}}>112 KB · uploaded just now</div>
                </div>
              </div>
              <span className="sk-btn tiny ghost">remove</span>
            </div>
          </div>
        </div>

        {/* preview side: what the LLM extracted */}
        <div className="sk-box thick" style={{padding:'18px 20px', background:'#fff'}}>
          <div className="sk-row" style={{justifyContent:'space-between', alignItems:'center'}}>
            <div className="sk-sub">extracted from your resume</div>
            <span className="sk-sub" style={{color:'var(--accent)'}}>LLM · please review</span>
          </div>
          <h2 className="sk-h2" style={{marginTop:6}}>does this look right?</h2>
          <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:4}}>
            we extracted these — edit anything wrong before continuing.
          </div>

          <div className="sk-col" style={{gap:9, marginTop:14}}>
            <div className="sk-box" style={{padding:'8px 12px'}}>
              <div className="sk-sub">role</div>
              <div className="sk-row" style={{justifyContent:'space-between', marginTop:2}}>
                <div className="sk-h4">CS senior · graduating may 2026</div>
                <span className="sk-sub" style={{color:'var(--pencil-soft)'}}>edit</span>
              </div>
            </div>
            <div className="sk-box" style={{padding:'8px 12px'}}>
              <div className="sk-sub">experience</div>
              <div className="sk-row" style={{flexWrap:'wrap', gap:5, marginTop:6}}>
                <span className="sk-chip">backend intern · stripe</span>
                <span className="sk-chip">RA · NLP lab</span>
                <span className="sk-chip">+ add</span>
              </div>
            </div>
            <div className="sk-box" style={{padding:'8px 12px'}}>
              <div className="sk-sub">stack (auto)</div>
              <div className="sk-row" style={{flexWrap:'wrap', gap:5, marginTop:6}}>
                <span className="sk-chip on">python</span>
                <span className="sk-chip on">go</span>
                <span className="sk-chip on">postgres</span>
                <span className="sk-chip on">react</span>
                <span className="sk-chip">aws</span>
                <span className="sk-chip">redis</span>
              </div>
            </div>
            <div className="sk-box fill-coral" style={{padding:'8px 12px'}}>
              <div className="sk-sub">inferred weak spots</div>
              <div className="sk-row" style={{flexWrap:'wrap', gap:5, marginTop:6}}>
                <span className="sk-chip">graphs</span>
                <span className="sk-chip">DP</span>
                <span className="sk-chip">system design</span>
              </div>
              <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:6}}>
                a guess — you'll confirm on the next step.
              </div>
            </div>
            <div className="sk-box" style={{padding:'8px 12px'}}>
              <div className="sk-sub">target companies (auto)</div>
              <div className="sk-row" style={{flexWrap:'wrap', gap:5, marginTop:6}}>
                <span className="sk-chip">FAANG-tier</span>
                <span className="sk-chip">infra startups</span>
                <span className="sk-chip">+ add</span>
              </div>
            </div>
          </div>

          <div className="sk-row" style={{justifyContent:'space-between', marginTop:18}}>
            <span className="sk-btn ghost">← back</span>
            <div className="sk-row" style={{gap:8}}>
              <span className="sk-btn">looks wrong, redo</span>
              <span className="sk-btn coral lg">confirm &amp; continue →</span>
            </div>
          </div>
        </div>
      </div>

      <div style={{padding:'14px 80px', borderTop:'1.5px dashed var(--line-soft)', display:'flex', justifyContent:'space-between', background:'var(--paper)'}}>
        <div className="sk-sub">5 of 7 · this is the LLM step</div>
        <div className="sk-sub">your file isn't shared with other users · never used for training</div>
      </div>
    </OBChrome>
  );
}

// ────────── C · skills + accountability (deterministic, condensed) ──────────
function OnboardingC() {
  return (
    <OBChrome step={4}>
      <div style={{padding:'48px 80px', display:'grid', gridTemplateColumns:'1fr', gap:18}}>
        <div className="sk-row" style={{gap:14, alignItems:'baseline'}}>
          <StepBadge kind="det" />
          <h1 className="sk-h1">a few quick taps</h1>
        </div>
        <div className="sk-sub lc" style={{color:'var(--pencil)'}}>
          tap to set. no typing. no AI in this step — just answers we use to draft your plan.
        </div>

        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:14, marginTop:14}}>
          <div className="sk-box" style={{padding:'14px 16px'}}>
            <div className="sk-sub">hours per week (be honest)</div>
            <div className="sk-row" style={{marginTop:14, alignItems:'center'}}>
              <span className="sk-sub">2</span>
              <div style={{flex:1, height:6, background:'var(--ink)', position:'relative', margin:'0 10px', borderRadius:3}}>
                <span style={{position:'absolute', left:'58%', top:-6, width:18, height:18, background:'var(--accent)', border:'2px solid var(--ink)', borderRadius:'50%'}}></span>
              </div>
              <span className="sk-sub">25</span>
            </div>
            <div className="sk-h2" style={{textAlign:'center', marginTop:8, color:'var(--accent)'}}>~ 15 hrs</div>
          </div>

          <div className="sk-box" style={{padding:'14px 16px'}}>
            <div className="sk-sub">accountability</div>
            <div className="sk-col" style={{gap:6, marginTop:10}}>
              <div className="sk-row" style={{justifyContent:'space-between', padding:'6px 10px', border:'1.5px solid var(--ink)', borderRadius:6}}>
                <span style={{fontSize:14}}>self only</span>
                <div style={{width:16, height:16, border:'1.5px solid var(--ink)', borderRadius:'50%'}}></div>
              </div>
              <div className="sk-row fill-coral" style={{justifyContent:'space-between', padding:'6px 10px', border:'2px solid var(--ink)', borderRadius:6, background:'rgba(255,90,60,0.18)'}}>
                <span style={{fontSize:14, fontWeight:700}}>weekly check-in</span>
                <div style={{width:16, height:16, border:'1.5px solid var(--ink)', borderRadius:'50%', background:'var(--accent)'}}></div>
              </div>
              <div className="sk-row" style={{justifyContent:'space-between', padding:'6px 10px', border:'1.5px solid var(--ink)', borderRadius:6}}>
                <span style={{fontSize:14}}>sponsor / parent (opt-in fields)</span>
                <div style={{width:16, height:16, border:'1.5px solid var(--ink)', borderRadius:'50%'}}></div>
              </div>
            </div>
          </div>

          <div className="sk-box" style={{padding:'14px 16px'}}>
            <div className="sk-sub">quiet hours</div>
            <div className="sk-row" style={{marginTop:10, gap:8, alignItems:'center'}}>
              <div className="sk-box" style={{padding:'4px 12px', boxShadow:'none'}}><div className="sk-h4">10pm</div></div>
              <span className="sk-sub">→</span>
              <div className="sk-box" style={{padding:'4px 12px', boxShadow:'none'}}><div className="sk-h4">8am</div></div>
            </div>
            <div className="sk-row" style={{marginTop:10, flexWrap:'wrap', gap:5}}>
              <span className="sk-chip">M</span><span className="sk-chip">T</span><span className="sk-chip">W</span>
              <span className="sk-chip">T</span><span className="sk-chip">F</span><span className="sk-chip on">no Sat work</span>
            </div>
          </div>
        </div>

        <div className="sk-box" style={{padding:'16px 18px', marginTop:6}}>
          <div className="sk-sub">skill self-rating · tap each to mark weak / ok / strong</div>
          <div className="sk-row" style={{flexWrap:'wrap', gap:6, marginTop:10}}>
            <span className="sk-chip coral">arrays · weak</span>
            <span className="sk-chip on">strings · ok</span>
            <span className="sk-chip coral">graphs · weak</span>
            <span className="sk-chip on">trees · ok</span>
            <span className="sk-chip coral">DP · weak</span>
            <span className="sk-chip on">SQL · ok</span>
            <span className="sk-chip">sysdesign</span>
            <span className="sk-chip">behavioral</span>
            <span className="sk-chip">concurrency</span>
            <span className="sk-chip">OOD</span>
            <span className="sk-chip dashed">+ topic</span>
          </div>
          <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:10}}>
            we pre-filled a few based on your resume. agree, edit, or wipe.
          </div>
        </div>
      </div>

      <div style={{padding:'14px 80px', borderTop:'1.5px dashed var(--line-soft)', display:'flex', justifyContent:'space-between', background:'var(--paper)'}}>
        <div className="sk-sub">4 of 7 · all deterministic</div>
        <div className="sk-row" style={{gap:8}}>
          <span className="sk-btn ghost">← back</span>
          <span className="sk-btn primary">next: resume upload →</span>
        </div>
      </div>
    </OBChrome>
  );
}

Object.assign(window, { OnboardingA, OnboardingB, OnboardingC });
