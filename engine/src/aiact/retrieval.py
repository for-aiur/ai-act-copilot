"""Bounded lexical retrieval with domain gates and diverse engineering topics."""
import re
import math
from .context import Budgets

DOMAINS = {
    'annex-iii-4-a': {'recruitment','recruit','resume','candidate','applicant','hiring','job','cv','employment','shortlist'},
    'annex-iii-1-a': {'biometric','biometrics','face','facial','identify','identification','watchlist','camera','gallery'},
    'article-50-1': {'chatbot','chat','assistant','conversation','interact','customer','reply'},
    'article-50-2': {'synthetic','deepfake','watermark','generative'},
}
# These gates select potentially relevant text, never determine applicability.
CHECKS = {
    'article-10-2': ('data', {'train','training','fit','dataset','data','label','labels','clean','cleaning','bias','features','resume'}),
    'article-10-3': ('data', {'validation','representative','missing','null','dropna','fillna','dataset','labels'}),
    'annex-iv-2-b': ('parameters', {'parameters','parameter','params','learning','depth','iterations','optimize','optimizer','hyperparameters'}),
    'annex-iv-2-d': ('training', {'train','training','fit','dataset','provenance','datasheet'}),
    'article-4a-1': ('privacy', {'sensitive','ethnicity','gender','racial','health','religion','retention','deletion','delete','pii','pseudonymisation'}),
    'article-14-4': ('oversight', {'shortlist','ranked','ranking','threshold','reject','approve','review','override','decision','decisions'}),
    'article-15-1': ('evaluation', {'predict','score','scores','accuracy','evaluate','evaluation','validation','test','metrics','threshold'}),
    'article-15-5': ('security', {'pickle','load','artifact','artifacts','poisoning','tampering','untrusted'}),
    'article-9-2': ('risk', {'risk','risks','monitor','monitoring','misuse'}),
    'article-12-1': ('logging', {'log','logs','logging','audit','trace'}),
    'article-11-1': ('documentation', {'documentation','version','modelcard','model_card'}),
    'article-13-1': ('instructions', {'instructions','limitations','interpret','explain'}),
    'article-26-2': ('deployer', {'deployer','operator','operations','deployment'}),
}


def retrieve(query: str, corpus: dict, budgets: Budgets = Budgets()) -> list[dict]:
    tokens=set(re.findall(r'[a-z]+',query.lower().replace('_',' ')))
    domains={sid for sid,words in DOMAINS.items() if tokens & words}
    if 'article-50-2' in domains and not (tokens & {'deepfake','watermark','generative'} or (tokens & {'synthetic'} and tokens & {'audio','video','content','text'} and tokens & {'generate','generated','generating'})):
        domains.remove('article-50-2')
    high_risk_context=bool(domains & {'annex-iii-4-a','annex-iii-1-a'})
    def lexical(section):
        words=set(re.findall(r'[a-z]+',section['text'].lower()))
        return len(tokens & words)
    primary=sorted([s for s in corpus['sections'] if s['id'] in domains],key=lambda s:(-len(tokens & DOMAINS[s['id']]),s['id']))
    if not primary:
        primary=[s for s in corpus['sections'] if s['id'] in {'article-6-2','article-6-3'}]
    # Local inverse document frequency supports broader article wording without embeddings.
    stopwords={'the','and','for','from','this','that','with','which','shall','system','systems','model','data','code','used','use','are','not','can','may','has','its','into','will','have','these','those','their','such','only','when','where','what','how','who','does','should'}
    query_words={t for t in tokens-stopwords if len(t)>2}
    documents=[set(re.findall(r'[a-z]+',s['text'].lower())) for s in corpus['sections']]
    frequencies={t:sum(t in words for words in documents) for t in query_words}
    candidates=[]
    fallback=[]
    for section in corpus['sections']:
        sid=section['id']
        if sid in {'article-26-10','article-14-5','article-12-3'} and not (tokens & {'biometric','biometrics','police','enforcement','criminal'}):
            continue
        if high_risk_context and sid in CHECKS:
            if sid == 'article-4a-1' and not (tokens & {'bias','fairness'} and tokens & {'sensitive','ethnicity','racial','health','religion','special'}):
                continue
            topic,signals=CHECKS[sid];hits=len(tokens & signals)
            if hits: candidates.append((hits*10+lexical(section),topic,section))
        elif high_risk_context and sid.startswith(('article-8-','article-9-','article-10-','article-11-','article-12-','article-13-','article-14-','article-15-','article-26-','annex-iv-')):
            hits=query_words & set(re.findall(r'[a-z]+',section['text'].lower()))
            if len(hits)>=2:
                score=sum(math.log((len(documents)+1)/(frequencies[t]+1)) for t in hits)
                if score>=6: fallback.append((score,section))
        elif 'article-50-2' in domains and sid in {'article-50-4','article-50-5'}:
            candidates.append((lexical(section),'disclosure',section))
    candidates.sort(key=lambda item:(-item[0],item[2]['id']))
    # First cover distinct topics, then related passages if space remains.
    diverse,related,topics=[],[],set()
    for item in candidates:
        if item[1] in topics: related.append(item[2])
        else: topics.add(item[1]);diverse.append(item[2])
    fallback.sort(key=lambda item:(-item[0],item[1]["id"]))
    selected=[];used=0
    for section in primary+diverse+related+[section for _,section in fallback]:
        size=len(section['text'].encode())
        if len(selected)<budgets.passages and used+size<=budgets.legal_bytes:
            selected.append(section);used+=size
    return selected
