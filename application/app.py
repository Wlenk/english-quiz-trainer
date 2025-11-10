#!/usr/bin/env python3
# app.py
import sys
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional, List, Any, Dict
import os
import json
import uuid
import datetime
import threading

if getattr(sys, "frozen", False):
    # 打包后 exe 所在目录
    APP_ROOT = os.path.dirname(sys.executable)
else:
    # 脚本运行时
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DICTS_ROOT = os.path.join(APP_ROOT, "dictionarys")  # 按你要求的位置
SESSIONS_DIR = os.path.join(APP_ROOT, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DICTS_ROOT, exist_ok=True)

app = FastAPI(title="Word Quiz API")
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 允许的前端来源
    allow_credentials=True,
    allow_methods=["*"],         # 允许所有 HTTP 方法
    allow_headers=["*"],         # 允许所有请求头
)
# In-memory session store (also persisted to sessions/)
_sessions_lock = threading.Lock()
_sessions: Dict[str, Dict[str, Any]] = {}

# ---- helpers ----
def list_dictionary_tree():
    """
    Walk dictionarys/ produce structure:
    {"config": {...}, "dictionarys":[{"name":..., "tag":..., "courses":[{"name":..., "words":"path", "activities":[{"uuid":..,"name":..,"words":"path"}]}]}]}
    """

    root = DICTS_ROOT
    result = {"config": {"title": "English Word Helper"}, "dictionarys": []}
    for dict_name in sorted(os.listdir(root)):
        dict_path = os.path.join(root, dict_name)
        if not os.path.isdir(dict_path):
            continue
        dict_obj = {"name": dict_name, "tag": dict_name, "courses": []}
        for course_name in sorted(os.listdir(dict_path)):
            course_path = os.path.join(dict_path, course_name)
            if not os.path.isdir(course_path):
                continue
            course_obj = {"name": course_name, "words": "", "activities": []}
            # default words.json path
            words_json = os.path.join(course_path, "words.json")
            if os.path.isfile(words_json):
                course_obj["words"] = os.path.relpath(words_json, root).replace("\\", "/")
            # scan mistakes folder
            mistakes_dir = os.path.join(course_path, "mistakes")
            if os.path.isdir(mistakes_dir):
                for fname in sorted(os.listdir(mistakes_dir)):
                    if not fname.lower().endswith(".json"):
                        continue
                    fpath = os.path.join(mistakes_dir, fname)
                    # create a uuid for activity (stable: use filename-based uuid5)
                    uuid_str = str(uuid.uuid5(uuid.NAMESPACE_URL, fpath))
                    activity_obj = {"uuid": uuid_str, "name": fname, "words": os.path.relpath(fpath, root).replace("\\", "/")}
                    course_obj["activities"].append(activity_obj)
            dict_obj["courses"].append(course_obj)
        result["dictionarys"].append(dict_obj)
    return result

def read_json_path(rel_or_path: str):
    """
    rel_or_path: path relative to DICTS_ROOT or absolute
    """
    if os.path.isabs(rel_or_path):
        p = rel_or_path
    else:
        p = os.path.join(DICTS_ROOT, rel_or_path)
    if not os.path.isfile(p):
        raise FileNotFoundError(p)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_atomic(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def make_session(words_list: List[dict], dictionary: str, course: str):
    sid = str(uuid.uuid4())
    session = {
        "session_id": sid,
        "dictionary": dictionary,
        "course": course,
        "created_at": datetime.datetime.now().isoformat(),
        "words": words_list,   # list of word dicts
        "pos": 0,
        "total": len(words_list),
        "wrong_indices": [],   # list of word entries (original dict)
        "answers": [],         # history of submissions
    }
    with _sessions_lock:
        _sessions[sid] = session
    # persist
    save_json_atomic(os.path.join(SESSIONS_DIR, f"{sid}.json"), session)
    return session

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    return "".join(s.split()).lower()

def find_word_by_index(words: List[dict], index: int):
    for w in words:
        if int(w.get("index")) == int(index):
            return w
    return None

# ---- API models ----
class CourseRequest(BaseModel):
    dictionary: str
    course: str
    activity: str  # "all" or uuid from activities

class ReportRequest(BaseModel):
    course: str               # e.g. "Part1/List1" or "Part1|List1" (we'll normalize)
    session_id: Optional[str] = None
    index: Optional[int] = None
    answer: Optional[str] = None
    timecost: Optional[float] = None
    done: Optional[bool] = False

# ---- endpoints ----
@app.get("/api/voice")
async def get_voice(dictionary: str, course: str, index: int):
    """
    返回指定单词的 mp3 文件
    文件路径规则: dictionarys/<dictionary>/<course>/voices/*_<index>.mp3
    例如: dictionarys/Part1/List1/voices/Part1_List1_1.mp3
    """
    voices_dir = os.path.join(DICTS_ROOT, dictionary, course, "voices")
    if not os.path.exists(voices_dir):
        raise HTTPException(status_code=404, detail="Voices directory not found")

    # 遍历目录找匹配的 mp3
    matched_file = None
    for fname in os.listdir(voices_dir):
        if fname.endswith(".mp3") and f"_{index}" in fname:
            matched_file = os.path.join(voices_dir, fname)
            break

    if not matched_file or not os.path.exists(matched_file):
        raise HTTPException(status_code=404, detail=f"Voice file for index {index} not found")

    return FileResponse(matched_file, media_type="audio/mpeg")
@app.get("/api/dictionaries")
def api_list_dictionaries():
    """
    返回整个词书列表与活动
    """
    return list_dictionary_tree()

@app.post("/api/course")
def api_get_course(req: CourseRequest):
    """
    请求某个 course 的词表或 activity（all / uuid）
    返回：对应的 words JSON（和你想要的一样），并生成 session_id
    response: { "session_id": "...", "data": {name, tag, words: [...] } }
    """
    # normalize paths
    dict_name = req.dictionary
    course_name = req.course
    activity = req.activity

    course_path = os.path.join(DICTS_ROOT, dict_name, course_name)
    if not os.path.isdir(course_path):
        raise HTTPException(status_code=404, detail="Course not found")

    # default words.json
    words_json_path = os.path.join(course_path, "words.json")
    if not os.path.isfile(words_json_path):
        raise HTTPException(status_code=404, detail="words.json not found for this course")

    # load main words
    try:
        main_json = read_json_path(words_json_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load words.json: {e}")

    # activity handling
    if activity == "all":
        words_list = main_json.get("words", [])
    else:
        # find activity file by matching uuid -> filename mapping created earlier
        mistakes_dir = os.path.join(course_path, "mistakes")
        if not os.path.isdir(mistakes_dir):
            raise HTTPException(status_code=404, detail="No activities found")
        # find matching file by uuid
        matched_file = None
        for fname in os.listdir(mistakes_dir):
            fpath = os.path.join(mistakes_dir, fname)
            u = str(uuid.uuid5(uuid.NAMESPACE_URL, fpath))
            if u == activity:
                matched_file = fpath
                break
        if not matched_file:
            raise HTTPException(status_code=404, detail="Activity uuid not found")
        try:
            act_json = read_json_path(matched_file)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load activity json: {e}")
        words_list = act_json.get("words", [])

    # create session
    session = make_session(words_list, dict_name, course_name)

    # respond with the wordlist and session id
    resp = {
        "session_id": session["session_id"],
        "name": main_json.get("name", f"{dict_name}-{course_name}"),
        "tag": main_json.get("tag", course_name),
        "words": words_list
    }
    return resp

@app.post("/api/report")
def api_report(req: ReportRequest):
    """
    Submit an answer or finish session.
    - course: "DictName/CourseName"
    - session_id: required unless creating new session is allowed (not here)
    - index, answer, timecost: for a single item submission
    - done: if true -> finalize and output mistake file
    Returns: {"correct":bool, "session_total":N, "session_wrong":M, ...}
    """
    # parse course parameter
    course_raw = req.course
    if "/" in course_raw:
        dict_name, course_name = course_raw.split("/", 1)
    elif "|" in course_raw:
        dict_name, course_name = course_raw.split("|", 1)
    else:
        raise HTTPException(status_code=400, detail="course should be 'Dictionary/Course'")

    sid = req.session_id
    if not sid:
        raise HTTPException(status_code=400, detail="session_id is required")

    with _sessions_lock:
        session = _sessions.get(sid)
    if not session:
        # try to load persisted session
        session_file = os.path.join(SESSIONS_DIR, f"{sid}.json")
        if os.path.isfile(session_file):
            try:
                session = read_json_path(session_file)
                with _sessions_lock:
                    _sessions[sid] = session
            except Exception:
                session = None
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    # verify course matches session
    if session.get("dictionary") != dict_name or session.get("course") != course_name:
        raise HTTPException(status_code=400, detail="session does not match course")

    # handle done
    if req.done:
        # finalize: write mistakes to mistakes dir
        mistakes = session.get("wrong_indices", [])
        if mistakes:
            mistakes_dir = os.path.join(DICTS_ROOT, dict_name, course_name, "mistakes")
            os.makedirs(mistakes_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%m_%d_%H_%M")
            # use tag+course in filename
            main_words_file = os.path.join(DICTS_ROOT, dict_name, course_name, "words.json")
            try:
                main_json = read_json_path(main_words_file)
                tag = main_json.get("tag", f"{dict_name}-{course_name}")
                name = main_json.get("name", f"{dict_name} {course_name}")
            except Exception:
                tag = f"{dict_name}-{course_name}"
                name = f"{dict_name} {course_name}"
            fname = f"mistake_{tag}_{ts}.json"
            fpath = os.path.join(mistakes_dir, fname)
            mistake_data = {"name": name, "tag": tag, "words": mistakes}
            save_json_atomic(fpath, mistake_data)
            return {"done": True, "mistakes_count": len(mistakes), "mistake_file": os.path.relpath(fpath, DICTS_ROOT).replace("\\","/")}
        else:
            return {"done": True, "mistakes_count": 0}

    # otherwise process answer submission
    if req.index is None or req.answer is None:
        raise HTTPException(status_code=400, detail="index and answer required when not done")

    # find word in session
    word = find_word_by_index(session.get("words", []), req.index)
    if not word:
        raise HTTPException(status_code=404, detail="word index not found in session")

    # judge correctness (answers list)
    answers = word.get("answer", []) or []
    user_norm = normalize_text(req.answer)
    correct_norms = [normalize_text(a) for a in answers]
    is_correct = user_norm in correct_norms

    # update session
    record = {
        "index": req.index,
        "user_answer": req.answer,
        "timecost": req.timecost if req.timecost is not None else 0.0,
        "correct": is_correct,
        "timestamp": datetime.datetime.now().isoformat()
    }
    session.setdefault("answers", []).append(record)
    if not is_correct:
        # store the original word entry into wrong_indices if not already present
        existing = [int(x.get("index")) for x in session.get("wrong_indices", [])]
        if int(req.index) not in existing:
            session.setdefault("wrong_indices", []).append(word)

    # persist session
    save_json_atomic(os.path.join(SESSIONS_DIR, f"{sid}.json"), session)
    with _sessions_lock:
        _sessions[sid] = session

    total = session.get("total", 0)
    wrong_count = len(session.get("wrong_indices", []))
    return {"correct": is_correct, "session_total": total, "session_wrong": wrong_count}

frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")