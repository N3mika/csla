from __future__ import annotations
import json, re, html
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import subprocess
from pathlib import Path
import shutil

def save_report_as_pdf(html_path, output_dir):
    html_path = Path(html_path).resolve()
    output_dir = Path(output_dir).resolve()
    pdf_path = output_dir / "----"

    # Find Microsoft Edge or Google Chrome
    browser_candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]

    browser = next(
        (str(p) for p in browser_candidates if p and Path(p).is_file()),
        None
    )

    if browser is None:
        print("PDF generation skipped: Chrome or Edge not found.")
        return None

    command = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--print-to-pdf=" + str(pdf_path),
        html_path.as_uri(),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            timeout=120,
            capture_output=True,
            text=True
        )

        if not pdf_path.exists():
            raise RuntimeError("Browser did not create the PDF.")

        print("PDF Report:", pdf_path)
        return pdf_path

    except Exception as e:
        print("PDF generation failed:", e)
        return None
    
INPUT_CSV = Path('----')
OUTPUT_DIR = Path('----')
MAX_LINK_GAP_ROWS = 4 

FEEDBACK = {'F:EC','F:R','F:CR','F:EL','F:MF','F:CC','F:Pr','F:Ack','F:NE'}
CORRECTIVE = {'F:EC','F:R','F:CR','F:EL','F:MF','F:CC','F:NE'}
UPTAKE = {'R:S','R:IR','R:Ack','R:NR'}
PROMPTS = {'P:I','P:IQ','P:CQ'}
ERRORS = {'Er:G','Er:L','Er:M','Er:EU'}
FAMILY = {'Instructor prompts':PROMPTS, 'Feedback':FEEDBACK, 'Uptake/repair':UPTAKE,
          'Learner prompts':{'SP','SP:I','SP:IQ','SP:CQ'}, 'Prompt response':{'PR'},
          'Classroom management':{'CM'}, 'Conversation management':{'CoM'},
          'Instructor answer':{'A'}, 'Instructor reaction':{'RN'}, 'Unknown':{'UNK'}}


LABEL_GLOSSARY = {
'P:I':('Instructor instruction','Directs or assigns learner production.'),'P:IQ':('Instructor information question','Requests information or an answer.'),'P:CQ':('Instructor clarification question','Requests clarification outside corrective feedback.'),
'F:EC':('Explicit correction','Overtly supplies a corrected form.'),'F:R':('Recast','Reformulates learner production without overt correction.'),'F:CR':('Clarification request','Signals a problem and requests clarification.'),'F:EL':('Elicitation','Invites learner to supply the target form.'),'F:MF':('Metalinguistic feedback','Comments on a language form or rule.'),'F:CC':('Confirmation check','Checks an interpretation or form.'),'F:Pr':('Praise','Positively evaluates learner performance.'),'F:Ack':('Feedback acknowledgement','Acknowledges or repeats an accepted learner form.'),'F:NE':('Negative evaluation','Marks production as incorrect without supplying a correction.'),
'A':('Instructor answer','Answers a learner question.'),'RN':('Instructor reaction','Responds to content rather than linguistic accuracy.'),'CM':('Classroom management','Organizes participation, logistics, or technology.'),'CoM':('Conversation management','Regulates conversational flow or backchannels.'),
'PR':('Prompt response','Learner responds to a prompt or task.'),'SP':('Student prompt','Learner initiates an interaction.'),'SP:I':('Student instruction','Learner directs an action.'),'SP:IQ':('Student information question','Learner asks for information.'),'SP:CQ':('Student clarification question','Learner asks for clarification or assistance.'),
'R:S':('Successful repair','Learner resolves a feedback-targeted problem.'),'R:IR':('Incomplete repair','Learner attempts but does not complete repair.'),'R:Ack':('Uptake acknowledgement','Learner acknowledges feedback without reformulation.'),'R:NR':('No uptake','No uptake before the interaction moves on.'),'UNK':('Unknown','Function cannot be determined reliably.'),
'Er:G':('Grammar error','One observable grammatical error.'),'Er:L':('Lexical error','One observable lexical error.'),'Er:M':('Multiple errors','Multiple observable grammatical or lexical errors.'),'Er:EU':('English utterance','Substantially English when Spanish is expected.')}
LEARNER_PALETTE=['#2563eb','#e76f51','#2a9d8f','#9b5de5','#e9a23b','#ef476f','#457b9d','#70ad47','#b56576','#008b8b']
def learner_visuals(d,out):
    import matplotlib.pyplot as plt
    q=d[d.speaker_role.eq('learner')].copy()
    if q.empty:return '',pd.DataFrame()
    q['learner_key']=q.speaker.str.strip().str.casefold()
    display=q.groupby('learner_key').speaker.agg(lambda x:x.value_counts().index[0]).to_dict()
    names=sorted(q.learner_key.unique())
    colors={k:LEARNER_PALETTE[i%len(LEARNER_PALETTE)] for i,k in enumerate(names)}
    rows=[]
    for k,g in q.groupby('learner_key'):
        rows.append(dict(learner=display[k],sentence_rows=len(g),words=int(g.word_count.sum()),turns=int(g.turn_number.nunique()) if 'turn_number' in g else None,
          prompt_response_rows=int(g.labels_list.map(lambda a:'PR' in a).sum()),uptake_rows=int(g.has_uptake.sum()),error_rows=int(g.has_error.sum()),error_rows_per_100_learner_rows=round(100*g.has_error.mean(),1),
          grammar_rows=int(g.errors_list.map(lambda a:'Er:G' in a).sum()),lexical_rows=int(g.errors_list.map(lambda a:'Er:L' in a).sum()),multiple_error_rows=int(g.errors_list.map(lambda a:'Er:M' in a).sum()),english_rows=int(g.errors_list.map(lambda a:'Er:EU' in a).sum())))
    stats=pd.DataFrame(rows).sort_values('sentence_rows',ascending=False)
    stats.to_csv(out/'learner_statistics.csv',index=False)
    labels=[display[k] for k in names]; x=np.arange(len(names)); barcolors=[colors[k] for k in names]
    def save(name):plt.tight_layout();plt.savefig(out/'charts'/name,dpi=170,bbox_inches='tight');plt.close()
    fig,ax=plt.subplots(figsize=(max(8,len(names)*1.25),4.4))
    counts=[sum(q.learner_key==k) for k in names]
    ax.bar(x,counts,color=barcolors);ax.set_xticks(x,labels,rotation=25,ha='right');ax.set_ylabel('Sentence rows');ax.set_title('Learner participation by speaker');save('learner_participation.png')
    fig,ax=plt.subplots(figsize=(max(8,len(names)*1.25),4.4))
    wc=[int(q.loc[q.learner_key==k,'word_count'].sum()) for k in names]
    ax.bar(x,wc,color=barcolors);ax.set_xticks(x,labels,rotation=25,ha='right');ax.set_ylabel('Approximate words');ax.set_title('Learner production (word count)');save('learner_words.png')
    fig,ax=plt.subplots(figsize=(max(8,len(names)*1.25),4.4))
    rates=[100*q.loc[q.learner_key==k,'has_error'].mean() for k in names]
    ax.bar(x,rates,color=barcolors);ax.set_xticks(x,labels,rotation=25,ha='right');ax.set_ylabel('Error-labeled rows per 100 learner rows');ax.set_title('Observed error-label incidence by learner');save('learner_error_rates.png')
    fig,ax=plt.subplots(figsize=(max(8,len(names)*1.25),4.8))
    bottom=np.zeros(len(names));types=[('Er:G','Grammar','#457b9d'),('Er:L','Lexical','#e9a23b'),('Er:M','Multiple','#9b5de5'),('Er:EU','English','#e76f51')]
    for code,label,color in types:
        vals=np.array([sum(code in a for a in q.loc[q.learner_key==k,'errors_list']) for k in names]);ax.bar(x,vals,bottom=bottom,label=label,color=color);bottom+=vals
    ax.set_xticks(x,labels,rotation=25,ha='right');ax.set_ylabel('Error-labeled rows');ax.set_title('Learner error category distribution');ax.legend(ncol=4,fontsize=8);save('learner_error_types.png')
    fig,ax=plt.subplots(figsize=(max(8,len(names)*1.25),4.6))
    metrics=[('PR','Prompt response','#2563eb'),('R:S','Successful repair','#2a9d8f'),('R:IR','Incomplete repair','#e76f51'),('R:Ack','Uptake acknowledgement','#9b5de5')]
    bottom=np.zeros(len(names))
    for code,label,color in metrics:
        vals=np.array([sum(code in a for a in q.loc[q.learner_key==k,'labels_list']) for k in names]);ax.bar(x,vals,bottom=bottom,label=label,color=color);bottom+=vals
    ax.set_xticks(x,labels,rotation=25,ha='right');ax.set_ylabel('Annotated row occurrences');ax.set_title('Learner response functions');ax.legend(fontsize=8);save('learner_response_types.png')
    return '<section><h2>Learner-level diagnostics</h2><p>Speaker names are grouped case-insensitively. Error incidence is the proportion of each learner\'s rows with an error label, not an assessment of proficiency. Counts reflect annotations, and reading aloud or task differences may affect comparisons.</p>'+''.join(f'<h3>{title}</h3><img src="charts/{name}">' for name,title in [('learner_participation.png','Participation'),('learner_words.png','Production'),('learner_error_rates.png','Error incidence'),('learner_error_types.png','Error types'),('learner_response_types.png','Response and uptake')])+'</section>',stats

def time_seconds(x):
    if pd.isna(x): return np.nan
    s=str(x).strip()
    try:
        parts=[float(t) for t in s.split(':')]
        if len(parts)==3: return parts[0]*3600+parts[1]*60+parts[2]
        if len(parts)==2: return parts[0]*60+parts[1]
    except ValueError: pass
    return np.nan

def tokens(x):
    if pd.isna(x): return []
    return [s.strip() for s in re.split(r'[,;|]',str(x)) if s.strip() and s.strip().lower() not in {'nan','none','[]'}]

def load(path):
    d=pd.read_csv(path,skip_blank_lines=True,encoding='utf-8-sig').copy()
    d.columns=[c.strip().lower() for c in d.columns]
    required={'sentence_id','start_time','end_time','speaker_role','speaker','sentence','labels','error_labels'}
    missing=required-set(d.columns)
    if missing: raise ValueError('Missing columns: '+', '.join(sorted(missing)))
    d['labels_list']=d['labels'].map(tokens)
    d['errors_list']=d['error_labels'].map(tokens)
    d['speaker_role']=d['speaker_role'].fillna('unknown').astype(str).str.strip().str.lower()
    d['speaker']=d['speaker'].fillna('Unknown').astype(str)
    d['sentence']=d['sentence'].fillna('').astype(str)
    d['start_sec']=d['start_time'].map(time_seconds)
    d['end_sec']=d['end_time'].map(time_seconds)
    d['word_count']=d['sentence'].str.findall(r"\b[\wÀ-ÿ]+(?:['’-][\wÀ-ÿ]+)*\b").str.len()
    d['has_feedback']=d['labels_list'].map(lambda a:bool(FEEDBACK.intersection(a)))
    d['has_corrective']=d['labels_list'].map(lambda a:bool(CORRECTIVE.intersection(a)))
    d['has_uptake']=d['labels_list'].map(lambda a:bool(UPTAKE.intersection(a)))
    d['has_prompt']=d['labels_list'].map(lambda a:bool(PROMPTS.intersection(a)))
    d['has_error']=d['errors_list'].map(lambda a:bool(ERRORS.intersection(a)))
    d['label_count']=d['labels_list'].map(len)
    d['row_index']=np.arange(len(d))
    return d

def evidence_row(d,i,kind,relation='',linked=None):
    r=d.iloc[i]
    return {'evidence_type':kind,'relation':relation,'sentence_id':str(r.sentence_id),
            'row_index':int(i),'start_time':str(r.start_time),'end_time':str(r.end_time),
            'speaker':r.speaker,'speaker_role':r.speaker_role,'sentence':r.sentence,
            'labels':', '.join(r.labels_list),'error_labels':', '.join(r.errors_list),
            'linked_sentence_id': '' if linked is None else str(d.iloc[linked].sentence_id)}

def link_to_next(d,source_mask,target_mask,source_role=None,target_role=None,max_gap=MAX_LINK_GAP_ROWS):
    """Heuristic: first qualifying row among the next max_gap rows, no other source event in between.
    Does not establish causal or semantic correspondence.
    """
    links=[]; unlinked=[]
    for i in range(len(d)):
        if not bool(source_mask[i]) or (source_role and d.iloc[i].speaker_role!=source_role):continue
        match=None
        for j in range(i+1,min(len(d),i+max_gap+2)):
            if bool(source_mask[j]) and (not source_role or d.iloc[j].speaker_role==source_role):break
            if bool(target_mask[j]) and (not target_role or d.iloc[j].speaker_role==target_role):
                match=j;break
        if match is None:unlinked.append(i)
        else:links.append((i,match))
    return links,unlinked

def chart_bar(counter,title,path,top=15):
    items=sorted(counter.items(),key=lambda kv:kv[1],reverse=True)[:top]
    if not items:return
    labels=[str(k) for k,v in items][::-1]; vals=[v for k,v in items][::-1]
    fig,ax=plt.subplots(figsize=(8.5,max(3.2,len(items)*.36+.8)))
    ax.barh(labels,vals)
    ax.set_title(title);ax.set_xlabel('Annotated row occurrences')
    for j,v in enumerate(vals):ax.text(v,j,f' {v}',va='center',fontsize=8)
    ax.set_xlim(0,max(vals)*1.16 if max(vals)>0 else 1)
    fig.tight_layout();fig.savefig(path,dpi=150,bbox_inches='tight');plt.close(fig)

def chart_timeline(d,path):
    usable=d.dropna(subset=['start_sec'])
    if usable.empty:return False
    max_t=max(1,float(usable['end_sec'].max()))
    edges=np.linspace(0,max_t,11)
    bins=np.minimum(np.searchsorted(edges,usable.start_sec.to_numpy(),side='right')-1,9)
    labels=['Prompt','Feedback','Uptake','Error']
    counts={lab:np.zeros(10,dtype=int) for lab in labels}
    for (_,r),b in zip(usable.iterrows(),bins):
        for lab,field in [('Prompt','has_prompt'),('Feedback','has_feedback'),('Uptake','has_uptake'),('Error','has_error')]:
            if r[field]:counts[lab][b]+=1
    fig,ax=plt.subplots(figsize=(10,4))
    for lab in labels:ax.plot(range(1,11),counts[lab],marker='o',label=lab)
    ax.set_xticks(range(1,11));ax.set_xlabel('Session decile by timestamp');ax.set_ylabel('Labeled rows')
    ax.set_title('Event distribution across lesson time (row counts, not duration)')
    ax.legend(ncol=4,fontsize=8);fig.tight_layout();fig.savefig(path,dpi=150);plt.close(fig)
    return True

def overlap_duration(d,role):
    q=d[(d.speaker_role==role)&d.start_sec.notna()&d.end_sec.notna()]
    intervals=sorted((float(a),float(b)) for a,b in zip(q.start_sec,q.end_sec) if b>=a)
    merged=[]
    for a,b in intervals:
        if not merged or a>merged[-1][1]:merged.append([a,b])
        else:merged[-1][1]=max(merged[-1][1],b)
    return round(sum(b-a for a,b in merged),1)

def generate(d,out):
    out.mkdir(parents=True,exist_ok=True)
    images=out/'charts';images.mkdir(exist_ok=True)
    main=Counter(x for a in d.labels_list for x in a)
    errors=Counter(x for a in d.errors_list for x in a)
    fb=Counter({x:main[x] for x in FEEDBACK if main[x]})
    prompts=Counter({x:main[x] for x in PROMPTS if main[x]})
    uptake=Counter({x:main[x] for x in UPTAKE if main[x]})
    fam=Counter({name:int(d.labels_list.map(lambda a:bool(v.intersection(a))).sum()) for name,v in FAMILY.items()})
    speakers=d.groupby(['speaker_role','speaker'],dropna=False).agg(rows=('sentence_id','size'),words=('word_count','sum')).reset_index()
    speakers.to_csv(out/'speaker_statistics.csv',index=False)
    freq=pd.DataFrame([{'label':k,'occurrences':v,'family':next((n for n,s in FAMILY.items() if k in s),'other')} for k,v in main.items()]).sort_values('occurrences',ascending=False)
    freq.to_csv(out/'label_frequencies.csv',index=False)
    pd.DataFrame([{'error_label':k,'occurrences':v} for k,v in errors.items()]).to_csv(out/'error_frequencies.csv',index=False)
    fb_links,fb_unlinked=link_to_next(d,d.has_feedback.to_numpy(),d.has_uptake.to_numpy(),'instructor','learner')
    err_links,err_unlinked=link_to_next(d,d.has_error.to_numpy(),d.has_corrective.to_numpy(),'learner','instructor')
    pr_links,pr_unlinked=link_to_next(d,d.has_prompt.to_numpy(),d.labels_list.map(lambda a:'PR' in a).to_numpy(),'instructor','learner')
    evidence=[]
    for kind,mask in [('feedback',d.has_feedback),('learner_error',d.has_error),('uptake',d.has_uptake),('prompt',d.has_prompt)]:
        evidence += [evidence_row(d,i,kind) for i,v in enumerate(mask) if v]
    for name,links in [('error_to_corrective_feedback',err_links),('feedback_to_uptake',fb_links),('prompt_to_prompt_response',pr_links)]:
        for i,j in links:evidence.append(evidence_row(d,i,'sequence_link',name,j))
    pd.DataFrame(evidence).to_csv(out/'evidence_index.csv',index=False)
    links=[]
    for name,pairs,missing in [('error_to_corrective_feedback',err_links,err_unlinked),('feedback_to_uptake',fb_links,fb_unlinked),('prompt_to_prompt_response',pr_links,pr_unlinked)]:
        for i,j in pairs:links.append({'relation':name,'source_id':d.iloc[i].sentence_id,'target_id':d.iloc[j].sentence_id,'source_row':i,'target_row':j,'gap_rows':j-i-1,'status':'matched_by_proximity'})
        for i in missing:links.append({'relation':name,'source_id':d.iloc[i].sentence_id,'target_id':'','source_row':i,'target_row':'','gap_rows':'','status':'no_candidate_in_window'})
    pd.DataFrame(links).to_csv(out/'sequence_links.csv',index=False)
    chart_bar(main,'Classroom-event labels',images/'label_frequency.png')
    chart_bar(fb,'Teacher feedback subtypes',images/'feedback_types.png')
    chart_bar(errors,'Learner error labels',images/'learner_errors.png')
    chart_bar(fam,'Classroom-event families (rows with family)',images/'event_families.png')
    chart_bar(uptake,'Learner uptake outcomes',images/'uptake_types.png')
    chart_timeline(d,images/'timeline.png')
    speaker_counter=Counter({f'{r.speaker_role}: {r.speaker}':int(r.rows) for r in speakers.itertuples()})
    chart_bar(speaker_counter,'Participation by speaker (sentence rows)',images/'participation.png')
    learner_html,learner_stats=learner_visuals(d,out)
    role_counts=d.speaker_role.value_counts().to_dict()
    end=d.end_sec.max();start=d.start_sec.min()
    duration=round(float(end-start),1) if pd.notna(end) and pd.notna(start) else None
    bad_labels=sorted(set(main)-set().union(*FAMILY.values()))
    bad_errors=sorted(set(errors)-ERRORS)
    warnings=[]
    if bad_labels:warnings.append('Unknown event labels: '+', '.join(bad_labels))
    if bad_errors:warnings.append('Unknown error labels: '+', '.join(bad_errors))
    if d.start_sec.isna().any() or d.end_sec.isna().any():warnings.append('Some timestamps could not be parsed.')
    if any(d.end_sec<d.start_sec):warnings.append('Some rows have end timestamps before start timestamps.')
    if (d[d.speaker_role=='instructor'].has_error).any():warnings.append('Some instructor rows contain learner error labels.')
    if d.duplicated(subset=['start_time','end_time']).any():warnings.append('Timestamp intervals repeat across sentence rows; row counts are not speaking time.')
    summary={
        'input_rows':len(d),'duration_seconds_from_timestamps':duration,'total_words_approx':int(d.word_count.sum()),
        'role_row_counts':role_counts,'instructor_interval_union_seconds_not_speech_time':overlap_duration(d,'instructor'),
        'learner_interval_union_seconds_not_speech_time':overlap_duration(d,'learner'),
        'rows_with_multiple_event_labels':int((d.label_count>1).sum()),
        'feedback_rows':int(d.has_feedback.sum()),'corrective_feedback_rows':int(d.has_corrective.sum()),
        'prompt_rows':int(d.has_prompt.sum()),'uptake_rows':int(d.has_uptake.sum()),
        'learner_error_rows':int(d.has_error.sum()),'unknown_rows':int(d.labels_list.map(lambda a:'UNK' in a).sum()),
        'feedback_subtypes':dict(sorted(fb.items())), 'error_subtypes':dict(sorted(errors.items())),
        'uptake_subtypes':dict(sorted(uptake.items())), 'prompt_subtypes':dict(sorted(prompts.items())),
        'sequence_proxies':{
          'error_to_corrective_feedback':{'sources':len(err_links)+len(err_unlinked),'matched':len(err_links),'unmatched':len(err_unlinked)},
          'feedback_to_uptake':{'sources':len(fb_links)+len(fb_unlinked),'matched':len(fb_links),'unmatched':len(fb_unlinked)},
          'prompt_to_prompt_response':{'sources':len(pr_links)+len(pr_unlinked),'matched':len(pr_links),'unmatched':len(pr_unlinked)}},
        'link_window_max_intervening_rows':MAX_LINK_GAP_ROWS,'warnings':warnings}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    def esc(s):return html.escape(str(s))
    def metric(label,value):return f'<div class="metric"><b>{esc(value)}</b><span>{esc(label)}</span></div>'
    def tbl(items):return '<table><tr><th>Measure</th><th>Value</th></tr>'+''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k,v in items)+'</table>'
    def examples(indices,heading,limit=7):
        s=f'<h3>{esc(heading)}</h3>'
        for i in indices[:limit]:
            r=d.iloc[i];s+=f'<div class="excerpt"><div class="meta">Sentence {esc(r.sentence_id)} | {esc(r.start_time)} | {esc(r.speaker_role)} | {esc(r.speaker)} | {esc(", ".join(r.labels_list))} {esc(", ".join(r.errors_list))}</div>{esc(r.sentence)}</div>'
        return s
    cards=''.join([metric('Transcript rows',len(d)),metric('Learner rows',role_counts.get('learner',0)),metric('Instructor rows',role_counts.get('instructor',0)),metric('Feedback-marked rows',summary['feedback_rows']),metric('Error-marked rows',summary['learner_error_rows']),metric('Uptake-marked rows',summary['uptake_rows'])])
    sections=[('participation.png','Participation'),('event_families.png','Event families'),('label_frequency.png','Event labels'),('feedback_types.png','Feedback strategies'),('learner_errors.png','Learner error categories'),('uptake_types.png','Uptake outcomes'),('timeline.png','Timeline')]
    timeline_note = ("The lesson is divided into 10 equal time intervals (1 = beginning, 10 = end). "
                     "Each line counts sentence rows tagged as Prompt, Feedback, Uptake, or Learner Error "
                     "within that interval. Higher points mean more tagged rows, not more speaking time. "
                     "These counts do not establish learner progress or feedback effectiveness.")
    imgs=''.join(f'<section><h2>{esc(title)}</h2><img src="charts/{name}" alt="{esc(title)}">'
                 + (f'<p class="chart-help">{esc(timeline_note)}</p>' if name=='timeline.png' else '')
                 + '</section>' for name,title in sections if (images/name).exists())
    instructor_names=sorted(d.loc[d.speaker_role.eq('instructor'),'speaker'].dropna().astype(str).str.strip().unique(),key=str.casefold)
    learner_names=sorted(d.loc[d.speaker_role.eq('learner'),'speaker'].dropna().astype(str).str.strip().unique(),key=str.casefold)
    def names_html(names):
        return ', '.join(esc(name) for name in names) if len(names) else 'Not identified'
    participants=(f'<div class="participants"><p><strong>Instructor:</strong> {names_html(instructor_names)}</p>'
                  f'<p><strong>Learners ({len(learner_names)}):</strong> {names_html(learner_names)}</p></div>')
    proxies=tbl([(k.replace('_',' ').title(),f"{v['matched']}/{v['sources']} source rows have a candidate within {MAX_LINK_GAP_ROWS} intervening rows") for k,v in summary['sequence_proxies'].items()])
    quality=tbl([('Unknown label rows',summary['unknown_rows']),('Multi-label rows',summary['rows_with_multiple_event_labels']),('Approximate word count',summary['total_words_approx']),('Duration from transcript endpoints (minutes)',round(duration/60,1) if duration is not None else 'Unavailable')])
    glossary='<section><h2>CSLA label glossary</h2><p>Short definitions of the supplied annotation codes. Classroom-event labels and learner-error labels are independent.</p><table><tr><th>Code</th><th>Full name</th><th>Short definition</th></tr>'+''.join(f'<tr><td><code>{esc(k)}</code></td><td>{esc(v[0])}</td><td>{esc(v[1])}</td></tr>' for k,v in LABEL_GLOSSARY.items())+'</table></section>'
    warning_html=''.join(f'<li>{esc(w)}</li>' for w in warnings)
    report=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>CSLA Diagnostic Report</title><style>
body{{font-family:Arial,Helvetica,sans-serif;max-width:1080px;margin:36px auto;padding:0 22px;color:#1e293b;background:#fff}}
h1{{font-size:30px}}h2{{font-size:21px;margin-top:36px}}h3{{font-size:16px}}p{{line-height:1.55}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.metric{{background:#f1f5f9;padding:17px;border-radius:8px;display:flex;flex-direction:column;gap:7px}}.metric b{{font-size:26px}}.metric span{{font-size:13px}}
.participants{{background:#f8fafc;border-radius:8px;padding:10px 16px;margin:14px 0 20px}}.participants p{{margin:5px 0}}.chart-help{{font-size:13px;color:#475569;background:#f1f5f9;border-radius:6px;padding:11px 14px;margin-top:8px}}section{{border-top:1px solid #e2e8f0;padding-top:12px}}img{{max-width:100%;height:auto;max-height:560px;object-fit:contain}}
table{{border-collapse:collapse;width:100%;margin:14px 0}}td,th{{padding:9px 12px;border-bottom:1px solid #e2e8f0;text-align:left}}th{{background:#f8fafc}}
.excerpt{{padding:12px;margin:9px 0;border-left:3px solid #64748b;background:#f8fafc;line-height:1.45}}.meta{{font-size:12px;color:#475569;margin-bottom:5px}}
.note{{border-left:4px solid #64748b;padding:12px 16px;background:#f8fafc}}@media print{{body{{max-width:100%}}section{{break-inside:avoid}}}}
</style></head><body><h1>SLA-LENS Classroom Diagnostic Report</h1><p>Deterministically generated from the supplied annotated transcript. All counts are row-based unless explicitly stated.</p>{participants}<div class="cards">{cards}</div>
<h2>Reading this report</h2><p class="note">Labels are model/human annotations supplied in the input, not independently verified facts. Sequence associations are proximity-based candidates, not confirmed pedagogical or causal links. Repeated timestamps make exact speaking-time estimates unreliable. No claims about learning gains, feedback effectiveness, or missed teaching opportunities are inferred.</p>
<h2>Session and data quality</h2>{quality}<ul>{warning_html}</ul>
<h2>Candidate interaction sequences</h2><p>Rule: find the first target event within {MAX_LINK_GAP_ROWS} intervening rows, stopping at another source event. These are candidate associations only. See sequence_links.csv and evidence_index.csv for full provenance.</p>{proxies}
{imgs}{learner_html}{glossary}<section><h2>Evidence examples</h2>{examples([i for i,v in enumerate(d.has_error) if v],'Learner-error rows')}{examples([i for i,v in enumerate(d.has_feedback) if v],'Feedback rows')}{examples([i for i,v in enumerate(d.has_uptake) if v],'Uptake rows')}</section>
<h2>Reproducibility</h2><p>Downloadable alongside this report: summary.json, label_frequencies.csv, error_frequencies.csv, speaker_statistics.csv, learner_statistics.csv, sequence_links.csv, and evidence_index.csv. The report contains no LLM-generated narrative.</p></body></html>'''
    (out/'index.html').write_text(report,encoding='utf-8')
    return summary

if __name__ == '__main__':
    d = load(INPUT_CSV)
    summary = generate(d, OUTPUT_DIR)

    html_path = OUTPUT_DIR / 'index.html'
    print('HTML Report:', html_path)

    save_report_as_pdf(html_path, OUTPUT_DIR)

    print(json.dumps(
        {k: summary[k] for k in [
            'input_rows',
            'feedback_rows',
            'uptake_rows',
            'learner_error_rows',
            'sequence_proxies'
        ]},
        indent=2
    ))
