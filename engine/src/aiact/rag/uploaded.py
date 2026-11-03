"""Bounded, explicitly uploaded text source. Never execute or import its code."""
import hashlib
import json
import math
import re
from pathlib import Path
from aiact.context import Budgets, Context, Source, collect
from aiact.providers import ReviewFailure

SOURCE_EXTENSIONS = {'.py','.js','.jsx','.ts','.tsx','.java','.go','.rs','.cs','.c','.cpp','.h','.hpp','.rb','.php','.swift','.kt','.scala','.sql','.sh','.r','.m','.txt'}

def validate_upload(filename, code, context=''):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_. -]{0,119}',filename) or Path(filename).suffix.lower() not in SOURCE_EXTENSIONS:
        raise ValueError('Choose a supported source file, not an archive or configuration file.')
    if '\x00' in code or any(ord(c)<32 and c not in '\n\r\t' for c in code):
        raise ValueError('Only UTF-8 text source files are supported.')
    if not code.strip():
        raise ValueError('The source file is empty.')
    if len(code.encode('utf-8'))+len(context.encode('utf-8'))>24_000:
        raise ValueError('Code and optional context must fit within 24 KB. Choose a smaller script or extract a section; nothing has been reviewed.')

def collect_upload(path, explicit_context='', budgets=Budgets()):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>budgets.source_bytes:
        raise ReviewFailure('unsupported_input','Upload must be one bounded regular source file.')
    try:
        code=path.read_text(encoding='utf-8')
        validate_upload(path.name,code,explicit_context)
    except (ValueError,UnicodeDecodeError) as exc:
        raise ReviewFailure('unsupported_input',str(exc)) from None
    if path.suffix.lower()=='.py':
        return collect(path,explicit_context,budgets)
    result=Context(root=path.parent)
    lines=code.splitlines()
    size=max(1,math.ceil(len(lines)/20))
    ranges=[(start,min(start+size-1,len(lines))) for start in range(1,len(lines)+1,size)]
    calls=re.findall(r'\b\w+\.(?:predict|generate|invoke|fit|encode)\s*\(',code)
    result.sources=[Source(path.name,code,ranges,calls)]
    result.coverage.scanned_files=[path.name]
    result.coverage.supported_languages=[path.suffix.lower().lstrip('.')]
    result.coverage.limitations.append('Uploaded text uses exact numbered lines; no language parser or code execution is used for this file type. Semantic support depends on the selected model.')
    result.fingerprint=hashlib.sha256(json.dumps({'filename':path.name,'code':code,'context':explicit_context},sort_keys=True).encode()).hexdigest()
    return result
