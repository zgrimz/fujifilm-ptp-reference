#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline structural checks. These do not establish factual or hardware correctness."""
import ast
import collections
import fnmatch
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
# Local tooling .gitignore keeps out of the repository. The checks never look inside: a virtual environment holds thousands of files that are not the record's.
SKIPPED_DIRS={'.git','.venv','venv','.pytest_cache','.obsidian'}
# Run output, captures and caches .gitignore keeps out of the repository. A stray one is reported so it is noticed before a push or an export.
STRAY_NAMES={'.DS_Store'}
STRAY_SUFFIXES=('.pcap','.pcapng','.pcap.gz','.pcapng.gz','.pyc')
STRAY_GLOBS=('bankprobe-*.json','bankprobe-*.txt')
STRAY_DIRS={'__pycache__','backups'}


def record_files(root):
    """Every file under root as a path relative to it, sorted, never looking inside SKIPPED_DIRS."""
    root=Path(root);files=[]
    for directory,subdirs,names in os.walk(root):
        subdirs[:]=[name for name in subdirs if name not in SKIPPED_DIRS]
        files.extend(Path(directory,name).relative_to(root) for name in names)
    return sorted(files)


def is_stray(relative):
    """True when .gitignore names this file: by name, by suffix (`*.raf` in any case, as .gitignore spells it), by glob, or by a directory on the way to it."""
    name=relative.name
    return (name in STRAY_NAMES or name.endswith(STRAY_SUFFIXES) or name.lower().endswith('.raf')
            or any(fnmatch.fnmatchcase(name,pattern) for pattern in STRAY_GLOBS) or bool(STRAY_DIRS.intersection(relative.parts[:-1])))


def stray_artifacts(root):
    """Files under root that .gitignore keeps out of the repository, relative to root."""
    return [path for path in record_files(root) if is_stray(path)]


def anchors(path):
    seen=collections.Counter();result=set();fenced=False
    for line in path.read_text(encoding='utf-8').splitlines():
        if re.match(r'^\s*(```|~~~)',line): fenced=not fenced;continue
        if fenced: continue
        match=re.match(r'^#{1,6}\s+(.+?)\s*#*$',line)
        if not match: continue
        title=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',match[1])
        title=re.sub(r'<[^>]+>','',title).lower()
        slug=''.join(c for c in title if c in '-_ ' or unicodedata.category(c)[0] in 'LN').replace(' ','-')
        count=seen[slug];seen[slug]+=1
        result.add(slug if not count else f'{slug}-{count}')
    return result


def check(root=ROOT):
    root=Path(root).resolve();errors=[];link_count=0;files=record_files(root);md=[root/path for path in files if path.suffix=='.md']
    for path in md:
        fenced=False;width=None
        for number,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
            loc=f'{path.relative_to(root)}:{number}'
            if re.match(r'^\s*(```|~~~)',line): fenced=not fenced;continue
            if fenced: continue
            if line.startswith('|') and line.endswith('|'):
                count=len(re.split(r'(?<!\\)\|',line))-2
                if width is not None and width!=count: errors.append(f'{loc}: table width {count}, expected {width}')
                width=count
            else: width=None
            if re.search(r'/Users/|/private/(tmp|var)/',line):
                errors.append(f'{loc}: private filesystem reference')
            for m in re.finditer(r'\[[^\]]*\]\(([^)]+)\)',line):
                target=m[1].split(' "')[0].strip('<>')
                if re.match(r'\w+:',target): continue
                name,_,fragment=target.partition('#')
                dest=(path.parent/unquote(name)).resolve() if name else path
                link_count+=1
                if not dest.is_relative_to(root): errors.append(f'{loc}: link escapes repo: {target}')
                elif not dest.exists(): errors.append(f'{loc}: missing target {target}')
                elif fragment and dest.suffix=='.md' and unquote(fragment) not in anchors(dest):
                    errors.append(f'{loc}: missing anchor {target}')
    py=[root/path for path in files if path.suffix=='.py']
    for path in py:
        try: ast.parse(path.read_text(encoding='utf-8'),filename=str(path.relative_to(root)))
        except SyntaxError as e: errors.append(str(e))
    errors.extend(f'export artifact should be excluded: {path}' for path in stray_artifacts(root))
    print(json.dumps({'markdown_files':len(md),'relative_links':link_count,'python_files':len(py),'errors':errors},indent=2))
    return 1 if errors else 0


if __name__=='__main__': sys.exit(check())
