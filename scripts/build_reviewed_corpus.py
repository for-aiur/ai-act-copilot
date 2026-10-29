"""Build selected official articles from explicitly downloaded Commission HTML.

No crawler or generated law. Inspect source selection before changing this list.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from aiact.corpus import OFFICIAL, Paragraphs, digest

ARTICLES = {'4a':'Special-category data for bias detection',6:'Classification',8:'High-risk requirements',9:'Risk management',10:'Data governance',
            11:'Technical documentation',12:'Logging',13:'Information to deployers',14:'Human oversight',
            15:'Accuracy robustness and cybersecurity',16:'Provider responsibilities',26:'Deployer responsibilities',50:'Transparency'}
ROOT = Path(__file__).resolve().parents[1]


def build(source_dir):
    original = json.loads((ROOT/'engine/src/aiact/data/corpus.json').read_text())
    original_quotes = {s['id']:s['supporting_quotes'] for s in original['sections']}
    original_quotes.update({
        'article-10-2': [
            'data collection processes and the origin of data, and in the case of personal data, the original purpose of the data collection;',
            'relevant data-preparation processing operations, such as annotation, labelling, cleaning, updating, enrichment and aggregation;',
            'appropriate measures to detect, prevent and mitigate possible biases identified according to point (f);'],
        'article-14-4': ['to decide, in any particular situation, not to use the high-risk AI system or to otherwise disregard, override or reverse the output of the high-risk AI system;'],
        'annex-iv-2-b': ['what the system is designed to optimise for, and the relevance of the different parameters;'],
        'annex-iv-2-d': ['how the data was obtained and selected; labelling procedures (e.g. for supervised learning), data cleaning methodologies (e.g. outliers detection);'],
        'article-4a-1': ['the special categories of personal data are deleted once the bias has been corrected or the personal data has reached the end of its retention period, whichever comes first;']
    })
    sections, checksums = [], {}
    def add(sid,title,paragraphs,page):
        text=' '.join(paragraphs)
        if 'Not present after the amendment.' in text:
            return
        quotes=original_quotes.get(sid)
        if not quotes:
            # Exact short source extract, not a synthetic summary. No model involved.
            first=next((p for p in paragraphs if len(p)>40),text)
            quote=re.sub(r'^\d+\.\s*','',first)
            quote=re.split(r'(?<=[.;])\s',quote,maxsplit=1)[0]
            if len(quote)>280:
                quote=quote[:280].rsplit(' ',1)[0]
            quotes=[quote]
        assert all(q in text and 10<=len(q)<=300 for q in quotes),sid
        sections.append(dict(id=sid,title=title,text=text,supporting_quotes=quotes,url=OFFICIAL+page,
            text_kind='binding_text_reproduced_by_commission',applicability_date=None,
            checksum=hashlib.sha256(text.encode()).hexdigest()))
    for page in ['annex-3','annex-4']+[f'article-{n}' for n in ARTICLES]:
        raw=(source_dir/(page+'.html')).read_bytes()
        parser=Paragraphs();parser.feed(raw.decode())
        ps=[p for p in parser.paragraphs if p not in {'AMENDED','NEW','Follow the European Commission'}]
        checksums[OFFICIAL+page]=hashlib.sha256(raw).hexdigest()
        if page in {'annex-3','annex-4'}:
            starts=[i for i,p in enumerate(ps) if re.match(r'^\d+\.\s',p)]
            assert len(starts)==(8 if page=='annex-3' else 9)
            roman='iii' if page=='annex-3' else 'iv'
            for pos,start in enumerate(starts):
                end=starts[pos+1] if pos+1<len(starts) else len(ps)
                number=re.match(r'^(\d+)\.',ps[start])[1]
                clauses=[i for i in range(start+1,end) if re.match(r'^\([a-z]\)\s',ps[i])]
                if not clauses:
                    add('annex-'+roman+'-'+number,'Annex '+roman.upper()+' '+number,ps[start:end],page)
                for j,i in enumerate(clauses):
                    last=clauses[j+1] if j+1<len(clauses) else end
                    letter=ps[i][1]
                    add(f'annex-{roman}-{number}-{letter}',f'Annex {roman.upper()} {number}({letter})',ps[i:last],page)
        elif page=='article-16':
            start=next(i for i,p in enumerate(ps) if p.startswith('Providers of high-risk AI systems shall'))
            add('article-16','Article 16: '+ARTICLES[16],ps[start:],page)
        else:
            starts=[i for i,p in enumerate(ps) if re.match(r'^\d+\.\s',p)]
            assert starts and ps[starts[0]].startswith('1.'),page
            for j,i in enumerate(starts):
                last=starts[j+1] if j+1<len(starts) else len(ps)
                paragraph=re.match(r'^(\d+)\.',ps[i])[1]
                add(f'{page}-{paragraph}',f'{page.replace("article-","Article ")}({paragraph}): '+ARTICLES[int(page.split('-')[1]) if page.split('-')[1].isdigit() else page.split('-')[1]],ps[i:last],page)
    data=dict(version='expanded-subset-2026-10-29',source_identity=original['source_identity'],
        retrieved_at='2026-10-29',verified_at='2026-10-29',source_checksums=checksums,
        scope_limits=[
            'Selected official text: Annexes III-IV and Articles 4a, 6, 8-16, 26 and 50; article/paragraph chunks, excluding deleted paragraph markers and nonbinding summaries.',
            'Stored text coverage is broader than evaluated use cases. Recruitment, remote biometrics and chatbot fixtures are tested; other uses require evaluation. No full AI Act coverage or independent legal review.',
            'Requirements for high-risk systems are conditional review questions, not a determination of classification, actor role, applicability dates, bias or dataset quality.',
            'Refresh re-verifies this selected text; changed text requires manual review and a package corpus revision. It does not discover amendments.'],
        sections=sections,checksum=digest(sections))
    target=ROOT/'engine/src/aiact/data';(target/'corpus.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    pages={s['id']:s['url'].removeprefix(OFFICIAL) for s in sections}
    (target/'section-pages.json').write_text(json.dumps(pages,indent=2)+'\n')
    (ROOT/'extensions/vscode/src/corpus-sections.ts').write_text('// Generated from the verified corpus by scripts/build_reviewed_corpus.py.\nexport const sectionPages: Record<string, string> = '+json.dumps(pages,indent=2)+';\n')
    print(len(sections),'passages;',sum(len(s['text'].split()) for s in sections),'words;',len(checksums),'official pages;',data['checksum'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-dir',type=Path,required=True)
    build(parser.parse_args().source_dir)
