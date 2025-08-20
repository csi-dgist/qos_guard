#!/usr/bin/env python3
import sys, pathlib, re
from typing import Dict, List

# ────────── ANSI 색 코드 ──────────
RED = "\033[31m"
BLUE = "\033[34m"
RESET = "\033[0m"

def color(txt: str, c: str) -> str:
    return f"{c}{txt}{RESET}"

# ────────── CLI 사용법 ──────────
USAGE = ("Usage: ros2 run check_qos check_qos_cli "
         "<pub.xml> <sub.xml> publish_period=<Nms> rtt=<Nms>")


# ────────── 유틸 ──────────
def load_text(p: pathlib.Path) -> str:
    if not p.exists():
        sys.exit(f"[ERROR] File not found: {p}")
    return p.read_text(encoding="utf-8", errors="ignore")

def parse_period(arg: str) -> int:
    if not arg.startswith("publish_period="):
        sys.exit("[ERROR] third argument must be publish_period=<Nms>")
    v = arg.split("=", 1)[1].strip().lower()
    if not v.endswith("ms") or not v[:-2].strip().isdigit():
        sys.exit("[ERROR] value must look like ‘40ms’")

    period_ms = int(v[:-2])
    globals()["publish_period_ms"] = period_ms   # ← 이 줄 추가 필수
    return period_ms
    
    
def parse_rtt(arg: str) -> int:
    if not arg.startswith("rtt="):
        sys.exit("[ERROR] fourth argument must be rtt=<Nms>")
    v = arg.split("=", 1)[1].strip().lower()
    if not v.endswith("ms") or not v[:-2].strip().isdigit():
        sys.exit("[ERROR] rtt value must look like ‘50ms’")

    rtt_ms = int(v[:-2])
    globals()["rtt_ns"] = rtt_ms * 1_000_000   # ns 단위로 저장
    return rtt_ms

# ────────── 태그 추출 패턴 ──────────
TAG_PATTERNS = {
    "reliability": re.compile(
        r"<\s*reliability\s*>.*?<\s*kind\s*>(\w+)\s*</kind\s*>.*?</\s*reliability\s*>",
        re.I | re.S),
        
    "history": re.compile(
        r"<\s*historyQos\s*>.*?<\s*kind\s*>(\w+)\s*</kind\s*>.*?</\s*historyQos\s*>",
        re.I | re.S),
        
    "history_depth": re.compile(
        r"<\s*historyQos\s*>.*?<\s*depth\s*>(\d+)</depth>", re.I | re.S),
    
    "durability": re.compile(
        r"<\s*durability\s*>.*?<\s*kind\s*>(\w+)\s*</kind\s*>.*?</\s*durability\s*>",
        re.I | re.S),
        
    "ownership": re.compile(                               
        r"<\s*ownership\s*>.*?<\s*kind\s*>(\w+)\s*</kind\s*>.*?</\s*ownership\s*>",
        re.I | re.S),
        
    "dest_order": re.compile(
        r"<\s*destinationOrder\s*>.*?<\s*kind\s*>(\w+)\s*</kind\s*>.*?</\s*destinationOrder\s*>",
        re.I | re.S),
        
    "max_samples": re.compile(
        r"<\s*resourceLimitsQos\s*>.*?<\s*max_samples\s*>(\d+)</max_samples>", re.I | re.S),

    "max_instances": re.compile(
        r"<\s*resourceLimitsQos\s*>.*?<\s*max_instances\s*>(\d+)</max_instances>", re.I | re.S),

    "max_samples_per_instance": re.compile(
        r"<\s*resourceLimitsQos\s*>.*?<\s*max_samples_per_instance\s*>(\d+)"
        r"</max_samples_per_instance>", re.I | re.S),
        
	"autodispose": re.compile(
	    r"<\s*writerDataLifecycle\s*>.*?"
	    r"<\s*autodispose_unregistered_instances\s*>\s*(\w+)\s*"
	    r"</autodispose_unregistered_instances\s*>.*?"
	    r"</\s*writerDataLifecycle\s*>",
	    re.I | re.S),
		    
	"autoenable": re.compile(
	    r"<\s*autoenable_created_entities\s*>\s*(\w+)\s*</autoenable_created_entities\s*>",
	    re.I | re.S),

    "liveliness": re.compile(
        r"<\s*liveliness\s*>.*?<\s*kind\s*>(.*?)</kind\s*>.*?</\s*liveliness\s*>",
        re.I | re.S),

    "nowriter_sec_r": re.compile(
        r"<\s*readerDataLifecycle\s*>.*?"
        r"<\s*autopurge_nowriter_samples_delay\s*>.*?"
        r"<\s*sec\s*>([^<]+)</sec\s*>",        
        re.I | re.S),

    "nowriter_nsec_r": re.compile(
        r"<\s*readerDataLifecycle\s*>.*?"
        r"<\s*autopurge_nowriter_samples_delay\s*>.*?"
        r"<\s*nanosec\s*>([^<]+)</nanosec\s*>",
        re.I | re.S),

    "userdata": re.compile(
    r"<\s*userData\s*>.*?<\s*value\s*>([^<]+)</value\s*>", re.I | re.S),
    
    
    
    "autopurge_disposed_samples_delay": re.compile(
    r"<\s*readerDataLifecycle\s*>.*?"
    r"<\s*autopurge_disposed_samples_delay\s*>.*?"
    r"<\s*sec\s*>(\d+)</sec\s*>", 
    re.I | re.S),



		 
}
    
# ────────── DEADLINE 헬퍼 ──────────
DEADLINE_RE = re.compile(
    r"<\s*deadline\s*>[^<]*?<\s*period\s*>"
    r"(?:[^<]*?<\s*sec\s*>(\d+)\s*</sec\s*>)?"          
    r"(?:[^<]*?<\s*nanosec\s*>(\d+)\s*</nanosec\s*>)?", 
    re.I | re.S)

def deadline_enabled(xml: str) -> bool:
    m = DEADLINE_RE.search(xml)
    if not m:
        return False
    sec  = int(m.group(1) or 0)
    nsec = int(m.group(2) or 0)
    return (sec != 0) or (nsec != 0)

def deadline_period_ns(xml: str) -> int | None:
    """
    DEADLINE period 를 ns 단위 정수로 반환.
    태그가 없으면 None,  sec==nsec==0 이면 0.
    """
    m = DEADLINE_RE.search(xml)
    if not m:
        return None          # DEADLINE 미설정
    sec  = int(m.group(1) or 0)
    nsec = int(m.group(2) or 0)
    return sec * 1_000_000_000 + nsec

# ────────── LIVELINESS 헬퍼 ──────────
LEASE_RE = re.compile(
    r"<\s*liveliness\s*>.*?<\s*lease_duration\s*>"
    r"(?:[^<]*?<\s*sec\s*>(\d+)\s*</sec\s*>)?"          # <sec>
    r"(?:[^<]*?<\s*nanosec\s*>(\d+)\s*</nanosec\s*>)?", # <nanosec>
    re.I | re.S)
    

def lease_duration_ns(xml: str) -> int | None:
    m = LEASE_RE.search(xml)
    if not m:
        return None
    sec  = int(m.group(1) or 0)
    nsec = int(m.group(2) or 0)
    return sec * 1_000_000_000 + nsec

ANNOUNCE_RE = re.compile(
    r"<\s*liveliness\s*>.*?<\s*announcement_period\s*>"
    r"(?:[^<]*?<\s*sec\s*>([^<]+)</sec\s*>)?"
    r"(?:[^<]*?<\s*nanosec\s*>([^<]+)</nanosec\s*>)?",
    re.I | re.S)

INF_SET = {"DURATION_INFINITY", "4294967295"}  

def parse_duration_field(txt: str | None) -> int | None:
    if not txt:
        return 0
    t = txt.strip().upper()
    if t in INF_SET:
        return None             
    return int(t)          


def announcement_period_ns(xml: str) -> int | None:
    m = ANNOUNCE_RE.search(xml)
    if not m:
        return None
    sec  = parse_duration_field(m.group(1))
    nsec = parse_duration_field(m.group(2))
    if sec is None or nsec is None:          
        return None
    return sec * 1_000_000_000 + nsec 
# ────────── LIFESPAN 헬퍼 ──────────

LIFESPAN_RE = re.compile(
    r"<\s*lifespan\s*>.*?</\s*lifespan\s*>",
    re.I | re.S)

# ────────── partition 헬퍼──────────
PART_ALL_RE = re.compile(
    r"<\s*partition\s*>.*?</\s*partition\s*>", re.I | re.S)
NAME_RE = re.compile(r"<\s*name\s*>([^<]+)</name\s*>", re.I | re.S)

def partition_list(xml: str) -> list[str]:
    blk = PART_ALL_RE.search(xml)
    if not blk:
        return [""]            # default partition
    names = NAME_RE.findall(blk.group(0))
    return [n.strip() for n in names] or [""]

def parse_profile(xml: str) -> Dict[str, str]:
    out = {}
    for k, pat in TAG_PATTERNS.items():
        m = pat.search(xml)
        out[k] = (m.group(1).upper() if m else "")

    # 추가: partition name 리스트
    out["partition_list"] = partition_list(xml)
    return out
# ────────── 규칙 1 : durability + RELIABLE ──────────
def rule_durability_needs_rel(_xml, q):
    non_volatile = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}
    if q["durability"] in non_volatile and q["reliability"] != "RELIABLE":
        return ("Invalid QoS: durability_kind is TRANSIENT_LOCAL/TRANSIENT/PERSISTENT "
                "but reliability_kind is not RELIABLE.\n"
                "Recommendation: use reliability_kind = RELIABLE with non-volatile durability.")
    return None
    
# ────────── 규칙 2 : durability + ownership ──────────
def rule_durability_exclusive(_xml, q):
    non_volatile = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}
    if q["durability"] in non_volatile and q["ownership"] == "EXCLUSIVE":
        return ("Error: Durable retransmission of outdated samples from previous owner may cause "
                "memory/network waste and delay new owner's schedule.\n"
                "Recommendation: use durability_kind = VOLATILE for ownership_kind = EXCLUSIVE.")
    return None
# ────────── 규칙 3 : durability + destinationOrder ──────────
def rule_dstorder_requires_rel_dur(_xml, q):
    if q["dest_order"] == "BY_SOURCE_TIMESTAMP":
        bad_rel = q["reliability"] != "RELIABLE"
        bad_dur = q["durability"] == "VOLATILE"
        if bad_rel or bad_dur:
            return ("Invalid QoS: destination_order_kind = BY_SOURCE_TIMESTAMP requires "
                    "reliability_kind = RELIABLE and durability_kind ≠ VOLATILE.\n"
                    "Recommendation: set reliability_kind = RELIABLE and choose "
                    "durability_kind = TRANSIENT_LOCAL (or higher) for stable ordering.")
    return None
# ────────── 규칙 4 : durability + deadline ──────────
def rule_deadline_vs_durability(xml, q):
    non_volatile = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}
    if deadline_enabled(xml) and q["durability"] in non_volatile:
        return ("QoS warning: durable samples may arrive late and reset the DEADLINE "
                "timer, potentially masking real timing violations.\n"
                "Recommendation: use VOLATILE durability when DEADLINE is critical, "
                "or relax / disable DEADLINE to tolerate replayed samples.")
    return None
# ────────── 규칙 5 : durability + ResourceLimits ──────────
def rule_keep_last_sample_budget(_xml, q):
    if q["history"] == "KEEP_LAST":
        depth  = int(q.get("history_depth")  or 0)
        max_s  = int(q.get("max_samples")    or 0)
        inst   = int(q.get("max_instances")  or 0)
        if max_s < depth * inst:
            return (f"KEEP_LAST({depth}) with {inst} instances exceeds "
                    f"max_samples ({max_s}).\n"
                    "Recommendation: set max_samples ≥ depth×instances, "
                    "or switch to KEEP_ALL.")
    return None
# ────────── 규칙 6 : durability + Keep_Last(depth<=1)──────────
def rule_durable_keep_last_depth(_xml, q):
    non_volatile = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}
    if q["durability"] in non_volatile and q["history"] == "KEEP_LAST":
        depth = int(q.get("history_depth") or 0)
        if depth <= 1:
            return ("Invalid QoS: TRANSIENT/PERSISTENT durability with KEEP_LAST(1) "
                    "retains only one sample, negating durable delivery.\n"
                    "Recommendation: set history depth > 1 or use KEEP_ALL.")
    return None
# ────────── 규칙 6-1 : durability + Keep_All + max_samples=INF──────────
def rule_keepall_durable_unlimited(_xml, q):
    non_volatile = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}
    unlimited_set = {"2147483647", "0", "-1"}           
    if q["durability"] in non_volatile and q["history"] == "KEEP_ALL":
        if q["max_samples"] in unlimited_set:
            return ("Warning: KEEP_ALL + TRANSIENT/PERSISTENT durability with unlimited "
                    "max_samples may cause uncontrolled storage growth.\n"
                    "Recommendation: set a finite max_samples or switch to KEEP_LAST.")
    return None
# ────────── 규칙 7 : durability + WriterDataLifecycle──────────
def rule_autodispose_vs_durability(_xml, q):
    non_volatile = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}
    auto =  q.get("autodispose", "").strip().upper() == "TRUE"
    if auto and q["durability"] in non_volatile:
        return ("Warning: Writer disposes are stored in durable cache; late joiners "
                "will receive DISPOSED instance state.\n"
                "Recommendation: set autodispose_unregistered_instances = FALSE, or "
                "use VOLATILE durability when dispose persistence is not desired.")
    return None

# ────────── 규칙 8 : deadline + liveliness ──────────
def rule_lease_vs_deadline(xml, _q):
    dl_m = DEADLINE_RE.search(xml)
    ld_m = LEASE_RE.search(xml)
    if not dl_m or not ld_m:
        return None

    # sec/nsec 원본 값 추출
    dl_sec, dl_nsec = int(dl_m.group(1) or 0), int(dl_m.group(2) or 0)
    ld_sec, ld_nsec = int(ld_m.group(1) or 0), int(ld_m.group(2) or 0)

    # 나노초 전체 계산
    dl_ns = dl_sec * 1_000_000_000 + dl_nsec
    ld_ns = ld_sec * 1_000_000_000 + ld_nsec

    if ld_ns < dl_ns:
        return (
            "lease_duration < deadline_period: DEADLINE timer may stop prematurely, hiding real-time deadline violations.\n"
            f"lease_duration  : {ld_sec}s {ld_nsec}ns ({ld_ns/1_000_000:.1f} ms)\n"
            f"deadline_period : {dl_sec}s {dl_nsec}ns ({dl_ns/1_000_000:.1f} ms)\n"
            "Recommendation  : set lease_duration ≥ deadline_period or relax the DEADLINE QoS."
        )
    return None
# ────────── 규칙 9 : deadline + reliability ──────────

def rule_deadline_with_best_effort(xml, q):

    if not deadline_enabled(xml):
        return None  

    if q.get("reliability", "").upper() == "BEST_EFFORT":
        return ("DEADLINE + BEST_EFFORT may cause false deadline misses due to packet loss.\n"
                "Recommendation: use RELIABLE for accurate detection.")
    return None
# ────────── 규칙 10 : ownership + deadline + reliability ──────────

def rule_exclusive_best_effort_deadline(xml, q):
    if not deadline_enabled(xml):
        return None

    if q["reliability"] == "BEST_EFFORT" and q["ownership"] == "EXCLUSIVE":
        return ("EXCLUSIVE + BEST_EFFORT may cause false DEADLINE misses and invalid ownership transitions.\n"
                "Recommendation: use RELIABLE for stable EXCLUSIVE ownership.")
    return None
# ────────── 규칙 11 : writerdatalifecycle + reliability ──────────

def rule_autodispose_with_best_effort(_xml, q):
    auto =  q.get("autodispose", "").strip().upper() == "TRUE"
    if q["reliability"] == "BEST_EFFORT" and auto:
        return ("WRITER_DATA_LIFECYCLE may be ineffective under BEST_EFFORT.\n"
                "Dispose/unregister messages can be lost.\n"
                "Recommendation: use RELIABLE when relying on autodispose_unregistered_instances.")
    return None

# ────────── 규칙 12 : deadline + lifespan ──────────
def rule_lifespan_vs_deadline(xml, _q):
    dl_m = DEADLINE_RE.search(xml)
    if not dl_m:
        return None

    # lifespan 블록만 추출
    lifespan_m = LIFESPAN_RE.search(xml)
    if not lifespan_m:
        return None
    lifespan_block = lifespan_m.group(0)

    # lifespan 내부에서 sec/nsec 추출
    sec_m  = re.search(r"<\s*sec\s*>(\d+)</sec\s*>", lifespan_block, re.I)
    nsec_m = re.search(r"<\s*nanosec\s*>(\d+)</nanosec\s*>", lifespan_block, re.I)

    if not sec_m and not nsec_m:
        return None  # 둘 다 없음

    ls_sec  = int(sec_m.group(1)) if sec_m else 0
    ls_nsec = int(nsec_m.group(1)) if nsec_m else 0
    dl_sec  = int(dl_m.group(1) or 0)
    dl_nsec = int(dl_m.group(2) or 0)

    ls_ns = ls_sec * 1_000_000_000 + ls_nsec
    dl_ns = dl_sec * 1_000_000_000 + dl_nsec

    if ls_ns < dl_ns:
        return (
            "Invalid QoS: LIFESPAN duration is shorter than DEADLINE period.\n"
            f"LIFESPAN : {ls_sec}s {ls_nsec}ns ({ls_ns/1_000_000:.1f} ms)\n"
            f"DEADLINE: {dl_sec}s {dl_nsec}ns ({dl_ns/1_000_000:.1f} ms)\n"
            "Recommendation: set lifespan ≥ deadline to ensure samples remain valid "
            "until the deadline timer expires.")
    return None

# ────────── 규칙 13 : publish_rate + lifespan + history ──────────

import math

def rule_history_vs_lifespan(xml, q):
    if "history_depth" not in q or not q["history_depth"].isdigit():
        return None

    # publish_period 값
    global_vars = globals()
    if "publish_period_ms" not in global_vars:
        return None
    publish_period_ms = global_vars["publish_period_ms"]
    publish_rate = 1000 / publish_period_ms  # Hz

    # lifespan sec/nsec 추출
    lifespan_m_sec  = re.search(r"<\s*lifespan\s*>.*?<\s*sec\s*>(\d+)</sec\s*>", xml, re.I | re.S)
    lifespan_m_nsec = re.search(r"<\s*lifespan\s*>.*?<\s*nanosec\s*>(\d+)</nanosec\s*>", xml, re.I | re.S)

    if not lifespan_m_sec and not lifespan_m_nsec:
        return None  # lifespan이 설정 안 되어 있으면 검사 생략

    ls_sec  = int(lifespan_m_sec.group(1)) if lifespan_m_sec else 0
    ls_nsec = int(lifespan_m_nsec.group(1)) if lifespan_m_nsec else 0
    lifespan_sec = ls_sec + (ls_nsec / 1_000_000_000)

    # 계산
    required_depth = math.ceil(lifespan_sec * publish_rate)
    actual_depth = int(q["history_depth"])

    if actual_depth < required_depth:
        return (f"Invalid QoS: history depth={actual_depth} is too small for lifespan={lifespan_sec:.3f}s at {publish_rate:.1f} Hz.\n"
                f"Recommendation: increase history depth to at least {required_depth} to retain samples during lifespan.")
    elif actual_depth > required_depth:
        return (f"Invalid QoS: history depth={actual_depth} exceeds what's needed for lifespan={lifespan_sec:.3f}s at {publish_rate:.1f} Hz.\n"
                f"Recommendation: reduce history depth to {required_depth} to conserve memory.")
    return None

# ────────── 규칙 14 : ownership + deadline──────────

def rule_exclusive_with_deadline(xml, q):
    if q.get("ownership", "").upper() != "EXCLUSIVE":
        return None

    if deadline_enabled(xml):  # DEADLINE이 설정되어 있는 경우만 경고
        return (
            "Invalid QoS: In EXCLUSIVE ownership mode, a DEADLINE miss may trigger "
            "automatic ownership transfer to another writer.\n"
            "Recommendation: disable DEADLINE (period = 0 or INFINITE) when using "
            "EXCLUSIVE ownership, or switch to SHARED ownership if DEADLINE must remain enabled."
        )
    return None

# ────────── 규칙 15 : lifespan + resourcelimits──────────

import math

def rule_buffer_capacity_vs_lifespan(xml, q):
    # 필수 항목 확인
    if "history_depth" not in q or not q["history_depth"].isdigit():
        return None
    if "max_samples" not in q or not q["max_samples"].isdigit():
        return None

    # publish_rate
    if "publish_period_ms" not in globals():
        return None
    publish_period_ms = globals()["publish_period_ms"]
    publish_rate = 1000 / publish_period_ms  # Hz

    # lifespan 추출
    lifespan_m_sec  = re.search(r"<\s*lifespan\s*>.*?<\s*sec\s*>(\d+)</sec\s*>", xml, re.I | re.S)
    lifespan_m_nsec = re.search(r"<\s*lifespan\s*>.*?<\s*nanosec\s*>(\d+)</nanosec\s*>", xml, re.I | re.S)

    if not lifespan_m_sec and not lifespan_m_nsec:
        return None

    ls_sec  = int(lifespan_m_sec.group(1)) if lifespan_m_sec else 0
    ls_nsec = int(lifespan_m_nsec.group(1)) if lifespan_m_nsec else 0
    lifespan_sec = ls_sec + (ls_nsec / 1_000_000_000)

    required_samples = math.ceil(lifespan_sec * publish_rate)
    depth = int(q["history_depth"])
    max_s = int(q["max_samples"])
    actual_capacity = min(depth, max_s)

    if actual_capacity < required_samples:
        return (f"Invalid QoS: buffer capacity = min(history={depth}, max_samples={max_s}) = {actual_capacity} is too small.\n"
                f"Lifespan = {lifespan_sec:.3f}s at {publish_rate:.1f} Hz requires ≥ {required_samples} samples.\n"
                f"Recommendation: increase history or max_samples to avoid overwriting samples before lifespan ends.")
    return None
# ────────── 규칙 16 : destination order + history depth ──────────

def rule_dest_order_vs_depth(_xml, q):
    if q["dest_order"] != "BY_SOURCE_TIMESTAMP":
        return None
    if not q.get("history_depth", "").isdigit():
        return None

    depth = int(q["history_depth"])
    if depth <= 1:
        return ("BY_SOURCE_TIMESTAMP with history depth ≤ 1 may drop out-of-order samples due to lack of reordering buffer.\n"
                "Recommendation: increase history depth to at least 2 when using BY_SOURCE_TIMESTAMP.")
    return None

# ────────── 규칙 17 : destination order(pub,sub)──────────
def rule_dest_order_compat(pub_q: dict, sub_q: dict) -> str | None:
    # 값 정규화 ─ 없으면 기본 BY_RECEPTION_TIMESTAMP 로 간주
    w_kind = (pub_q.get("dest_order", "") or "BY_RECEPTION_TIMESTAMP").strip().upper()
    r_kind = (sub_q.get("dest_order", "") or "BY_RECEPTION_TIMESTAMP").strip().upper()

    # Writer가 BY_RECEPTION, Reader가 BY_SOURCE 인 경우에만 경고
    if w_kind == "BY_RECEPTION_TIMESTAMP" and r_kind == "BY_SOURCE_TIMESTAMP":
        return ("Incompatible destination_order_kind: Writer='BY_RECEPTION_TIMESTAMP', "
                "Reader='BY_SOURCE_TIMESTAMP'.\n"
                "Reader expects stricter BY_SOURCE_TIMESTAMP ordering than Writer provides.\n"
                "Recommendation: set writer destination_order_kind = BY_SOURCE_TIMESTAMP, "
                "or relax reader requirement to BY_RECEPTION_TIMESTAMP.")
    return None

# ────────── 규칙 18 : ownership(pub,sub)──────────
def rule_ownership_compat(pub_q: dict, sub_q: dict) -> str | None:
    r_kind = (sub_q.get("ownership", "") or "SHARED").strip().upper()
    w_kind = (pub_q.get("ownership", "") or "SHARED").strip().upper()

    if r_kind == "EXCLUSIVE" and w_kind != "EXCLUSIVE":
        return ("Reader requests EXCLUSIVE ownership but Writer is not EXCLUSIVE.\n"
                "Data-instance hand-over rules will not be honoured.\n"
                "Recommendation: set writer ownership_kind to EXCLUSIVE to match "
                "the reader, or change reader to SHARED.")
    return None
# ────────── 규칙 19 : reliability(pub,sub)──────────

RELIABILITY_LEVEL = {"BEST_EFFORT": 0, "RELIABLE": 1}   # 숫자가 클수록 강함

def rule_reliability_compat(pub_q: dict, sub_q: dict) -> str | None:
    """Writer( PUB ) 가 Reader( SUB ) 요구보다 약한 신뢰성을 제공할 때 경고"""
    w_kind = (pub_q.get("reliability", "") or "BEST_EFFORT").strip().upper()
    r_kind = (sub_q.get("reliability", "") or "BEST_EFFORT").strip().upper()

    w_lvl = RELIABILITY_LEVEL.get(w_kind, 0)
    r_lvl = RELIABILITY_LEVEL.get(r_kind, 0)

    if w_lvl < r_lvl:   # Writer < Reader  → 호환 불가
        return (f"Incompatible reliability_kind: Writer='{w_kind}', Reader='{r_kind}'.\n"
                "Reader expects RELIABLE delivery but Writer is BEST_EFFORT.\n"
                "Recommendation: set writer reliability_kind = RELIABLE, "
                "or relax reader requirement to BEST_EFFORT.")
    return None
# ────────── 규칙 20 : HISTORY──────────
def rule_keep_last_depth_positive(_xml, q):
    if q.get("history", "").strip().upper() != "KEEP_LAST":
        return None                        # KEEP_ALL 이면 검사-제외

    depth_txt = q.get("history_depth", "").strip()
    if not depth_txt.isdigit():            # depth 가 없거나 숫자가 아님 → 오류로 처리
        return ("KEEP_LAST requires a positive depth, but depth is missing or not numeric.")
    depth = int(depth_txt)

    if depth <= 0:
        return ("Invalid QoS: KEEP_LAST requires depth > 0 but depth is "
                f"{depth}.\nRecommendation: set <historyQos><depth> to a "
                "positive integer (e.g. 1, 2 …).")
    return None
# ────────── 규칙 21 : HISTORY─+ resourcelimits─────────
def rule_history_vs_max_per_instance(_xml, q):
    hist_kind = q.get("history", "").strip().upper()
    depth_txt = q.get("history_depth", "").strip()
    mpi_txt   = q.get("max_samples_per_instance", "").strip() or "0"

    depth = int(depth_txt) if depth_txt.isdigit() else 0
    mpi   = int(mpi_txt)   if mpi_txt.isdigit()   else 0

    # ── R1 : KEEP_LAST  depth ≤ mpi ──────────────────────────
    if hist_kind == "KEEP_LAST" and depth > mpi:
        return (f"Invalid QoS: KEEP_LAST depth={depth} exceeds "
                f"max_samples_per_instance={mpi}.\n"
                "Recommendation: increase max_samples_per_instance "
                "or reduce history depth.")

    # ── R2 : KEEP_ALL   mpi > 0  ────────────────────────────
    if hist_kind == "KEEP_ALL" and mpi == 0:
        return ("Invalid QoS: KEEP_ALL with max_samples_per_instance=0 "
                "stores no samples at all.\n"
                "Recommendation: set max_samples_per_instance to a positive value.")
    return None
# ────────── 규칙 22 : Durability(pub,sub)─────────

DURABILITY_LEVEL = {
    "VOLATILE":         0,
    "TRANSIENT_LOCAL":  1,
    "TRANSIENT":        2,
    "PERSISTENT":       3,
}

def rule_durability_compat(pub_q: dict, sub_q: dict) -> str | None:
    """
    Writer ↔ Reader durability 호환성 검사
    Writer 레벨 < Reader 레벨 → 경고
    """
    w_kind = (pub_q.get("durability", "") or "VOLATILE").strip().upper()
    r_kind = (sub_q.get("durability", "") or "VOLATILE").strip().upper()

    w_lvl = DURABILITY_LEVEL.get(w_kind, 0)
    r_lvl = DURABILITY_LEVEL.get(r_kind, 0)

    if w_lvl < r_lvl:
        # 메시지 작성
        return (f"Incompatible durability_kind: Writer='{w_kind}', Reader='{r_kind}'.\n"
                "Reader expects stronger durability than Writer provides.\n"
                "Recommendation: raise writer durability_kind "
                f"to at least '{r_kind}', or lower reader requirement.")
    return None
# ────────── 규칙 23 : Deadline(pub,sub)─────────

def rule_deadline_period_compat(pub_xml: str, sub_xml: str) -> str | None:
    w_ns = deadline_period_ns(pub_xml)
    r_ns = deadline_period_ns(sub_xml)

    # Reader가 DEADLINE을 아예 안 쓰면 어떤 Writer 값도 허용
    if r_ns is None:
        return None

    # Writer가 DEADLINE이 없는데 Reader는 요구 → 불일치
    if w_ns is None:
        return ("Incompatible DEADLINE: Reader specifies a DEADLINE period "
                "but Writer has none.\nRecommendation: add a DEADLINE period "
                "to the Writer that is ≤ Reader’s requirement "
                "or remove DEADLINE from the Reader.")

    if r_ns != 0 and w_ns > r_ns:
        # Writer 주기가 Reader 요구보다 큼 (느림)
        return (f"Incompatible DEADLINE periods: Writer={w_ns/1e9:.3f}s "
                f"> Reader={r_ns/1e9:.3f}s.\n"
                "Recommendation: shorten Writer DEADLINE period "
                "or relax Reader requirement.")
    return None
# ────────── 규칙 24 : Liveliness(pub,sub)─────────

LIVELINESS_PRIORITY = {
    "AUTOMATIC": 0,
    "MANUAL_BY_PARTICIPANT": 1,
    "MANUAL_BY_TOPIC": 2,
}

def rule_liveliness_compat(pub_xml: str, sub_xml: str,
                           pub_q: dict, sub_q: dict) -> str | None:
    # ── kind 비교 ───────────────────────────────────────────
    w_kind = (pub_q.get("liveliness", "") or "AUTOMATIC").strip().upper()
    r_kind = (sub_q.get("liveliness", "") or "AUTOMATIC").strip().upper()

    w_lvl  = LIVELINESS_PRIORITY.get(w_kind, 0)
    r_lvl  = LIVELINESS_PRIORITY.get(r_kind, 0)

    if w_lvl < r_lvl:   # Writer 강도 < Reader 요구
        return (f"Incompatible liveliness_kind: Writer='{w_kind}', "
                f"Reader='{r_kind}'.\n"
                "Reader expects stricter liveliness than Writer provides.\n"
                "Recommendation: raise writer liveliness_kind "
                f"to '{r_kind}' or lower reader requirement.")

    # ── lease_duration 비교 ────────────────────────────────
    w_lease = lease_duration_ns(pub_xml)
    r_lease = lease_duration_ns(sub_xml)

    # Reader가 lease_duration을 지정하지 않았다면 통과
    if r_lease is None:
        return None
    # Writer가 lease_duration이 없으면 불일치
    if w_lease is None:
        return ("Incompatible liveliness lease_duration: Reader specifies a "
                "lease_duration but Writer has none.")

    if w_lease > r_lease:  # Writer 주기가 더 길면 (갱신 빈도가 낮음) 문제
        return (f"Incompatible liveliness lease_duration: "
                f"Writer={w_lease/1e9:.3f}s > Reader={r_lease/1e9:.3f}s.\n"
                "Recommendation: shorten writer lease_duration or relax "
                "reader requirement.")
    return None
# ────────── 규칙 25 : writerdatalifecycle + readerdatalifecycle(pub,sub)─────────
INF_SET = {"DURATION_INFINITY", "4294967295"}  # Fast DDS 의 0xFFFFFFFF 값 포함

def is_inf(txt: str | None) -> bool:
    return txt and txt.strip().upper() in INF_SET

def rule_nowriter_autodispose_cross(pub_q: dict, sub_q: dict) -> str | None:

    auto_off = pub_q.get("autodispose", "").strip().upper() == "FALSE"

    sec_txt  = sub_q.get("nowriter_sec_r", "")
    nsec_txt = sub_q.get("nowriter_nsec_r", "")

    # Reader delay 가 없으면 검사할 필요 없음
    if not sec_txt and not nsec_txt:
        return None

    # Reader delay 가 무한(또는 0) ?
    inf_delay  = is_inf(sec_txt)  or is_inf(nsec_txt)
    zero_delay = ((sec_txt.strip() == "0" or sec_txt == "") and
              (nsec_txt.strip() == "0" or nsec_txt == ""))


    if auto_off and (inf_delay or zero_delay):
        return ("Invalid QoS: autodispose_unregistered_instances=FALSE in the Writer "
                "while Reader autopurge_nowriter_samples_delay is INFINITE/0.\n"
                "Samples may never be purged when all writers disappear, causing "
                "unbounded memory growth.\n"
                "Recommendation: enable autodispose_unregistered_instances in the Writer "
                "or set a finite autopurge_nowriter_samples_delay in the Reader.")
    return None
# ────────── 규칙 26 : reliability + ownership ─────────

def rule_best_effort_exclusive(_xml, q):

    if (q.get("reliability", "").strip().upper() == "BEST_EFFORT" and
        q.get("ownership",   "").strip().upper() == "EXCLUSIVE"):
        return ("BEST_EFFORT reliability is incompatible with EXCLUSIVE ownership.\n"
                "Recommendation: use RELIABLE reliability_kind or switch ownership_kind to SHARED.")
    return None
# ────────── 규칙 27 : liveliness ─────────

def rule_announce_vs_lease(xml, q):
    # 적용 범위: AUTOMATIC, MANUAL_BY_PARTICIPANT
    live_kind = q.get("liveliness", "").strip().upper()
    if live_kind not in {"AUTOMATIC", "MANUAL_BY_PARTICIPANT"}:
        return None

    # lease_duration ns (총합) + 원본 sec/nsec
    ld_m = LEASE_RE.search(xml)
    if not ld_m:
        return None
    ld_sec  = int(ld_m.group(1) or 0)
    ld_nsec = int(ld_m.group(2) or 0)
    lease_ns = ld_sec * 1_000_000_000 + ld_nsec

    # announcement_period ns (총합) + 원본 sec/nsec
    ann_m = ANNOUNCE_RE.search(xml)
    if not ann_m:
        return None
    ann_sec_raw  = ann_m.group(1)
    ann_nsec_raw = ann_m.group(2)

    # 무한(INF) 값은 검사에서 제외
    if (ann_sec_raw and ann_sec_raw.strip().upper() in INF_SET) or \
       (ann_nsec_raw and ann_nsec_raw.strip().upper() in INF_SET):
        return None

    ann_sec  = int(ann_sec_raw or 0)
    ann_nsec = int(ann_nsec_raw or 0)
    ann_ns   = ann_sec * 1_000_000_000 + ann_nsec

    # 오류 조건: lease ≤ announce
    if lease_ns <= ann_ns:
        return (f"Invalid QoS: liveliness lease_duration "
                f"{ld_sec}s {ld_nsec}ns "
                f"≤ announcement_period "
                f"{ann_sec}s {ann_nsec}ns .\n"
                "Recommendation: set lease_duration > announcement_period.")
    return None
# ────────── 규칙 28 : Partition & partition ─────────
def rule_partition_overlap(pub_xml: str, sub_xml: str) -> str | None:
    w_parts = set(partition_list(pub_xml))
    r_parts = set(partition_list(sub_xml))

    if w_parts.isdisjoint(r_parts):     
        return ("No matching partition names between Writer and Reader; "
                "data exchange will not occur.\n"
                f"Writer partitions : {sorted(w_parts)}\n"
                f"Reader partitions : {sorted(r_parts)}\n"
                "Recommendation: configure at least one identical <partition><name> "
                "string on both sides.")
    return None
# ────────── 규칙 29 : Partition & userdata─────────
def rule_partition_userdata_key(pub_q: dict, sub_q: dict) -> str | None:
    w_part = pub_q.get("partition", "").strip()
    w_ud   = pub_q.get("userdata",  "").strip()
    r_part = sub_q.get("partition", "").strip()
    r_ud   = sub_q.get("userdata",  "").strip()

    if (w_part, w_ud) != (r_part, r_ud):
        return ("Partition or user_data change alters publication key; "
                "ACL ignore_*() filters may mismatch, causing unintended allow or block.\n"
                f"Writer key : ({w_part!r}, {w_ud!r})\n"
                f"Reader key : ({r_part!r}, {r_ud!r})\n"
                "Recommendation: configure identical partition & user_data, or "
                "update ACL rules accordingly.")
    return None
# ────────── 규칙 30 : Partition &  ─────────
NON_VOLATILE = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}

def rule_durable_partition_miss(pub_xml: str, sub_xml: str,
                                pub_q: dict, sub_q: dict) -> str | None:
    if pub_q.get("durability", "").strip().upper() not in NON_VOLATILE:
        return None                       # VOLATILE 이면 해당 없음

    w_parts = set(partition_list(pub_xml))
    r_parts = set(partition_list(sub_xml))
    if w_parts.isdisjoint(r_parts):
        return ("Durable samples are retransmitted only to Readers in the same "
                "partition. Writer partitions and Reader partitions share no "
                "common name, so late-joiner will start with an empty cache.\n"
                f"Writer partitions : {sorted(w_parts)}\n"
                f"Reader partitions : {sorted(r_parts)}\n"
                "Recommendation: configure at least one identical partition name "
                "or use VOLATILE durability if replay is not required.")
    return None
# ────────── 규칙 31 : Partition & deadline ─────────
def rule_deadline_partition_reset(pub_xml: str, sub_xml: str) -> str | None:
    if not deadline_enabled(sub_xml):     # Reader가 DEADLINE 미사용
        return None

    w_parts = set(partition_list(pub_xml))
    r_parts = set(partition_list(sub_xml))
    if w_parts.isdisjoint(r_parts):
        return ("Partition mismatch causes the Reader to perceive the Writer as "
                "a ‘new’ instance, resetting the DEADLINE timer. Miss detection "
                "may be masked or delayed.\n"
                f"Writer partitions : {sorted(w_parts)}\n"
                f"Reader partitions : {sorted(r_parts)}\n"
                "Recommendation: share at least one partition or disable DEADLINE "
                "if Writer mobility across partitions is expected.")
    return None
# ────────── 규칙 32 : durability + entityfactory─────────

def rule_autoenable_vs_volatile_reader(_xml, q):
    auto_off   = q.get("autoenable", "").strip().upper() == "FALSE"
    is_volatile = q.get("durability", "").upper() == "VOLATILE"

    if auto_off and is_volatile:
        return ("QoS warning: autoenable_created_entities=false while durability_kind=VOLATILE.\n"
                "Late-enabled DataReaders will MISS all samples published before enable().\n"
                "Recommendation: set autoenable_created_entities=true, or switch to "
                "TRANSIENT_LOCAL (or higher) durability to retain data for late joiners.")
    return None


# ────────── 규칙 추가─────────
# ────────── 규칙 2 : resourcelimits─────────
def rule_max_samples_vs_per_instance(_xml, q):
    max_s_txt = q.get("max_samples", "").strip()
    mpi_txt   = q.get("max_samples_per_instance", "").strip()

    if not max_s_txt.isdigit() or not mpi_txt.isdigit():
        return None   # 둘 중 하나라도 설정 안 되어 있으면 검사하지 않음

    max_s = int(max_s_txt)
    mpi   = int(mpi_txt)

    if max_s < mpi:
        return (f"Invalid QoS: max_samples ({max_s}) is less than "
                f"max_samples_per_instance ({mpi}).\n"
                "This setting prevents even a single instance from storing the expected number of samples.\n"
                "Recommendation: increase max_samples ≥ max_samples_per_instance.")
    return None


# ────────── 규칙 4 : resourcelimits + destination order─────────
def rule_destorder_keepall_mpi(xml, q):
    if q.get("dest_order", "").upper() != "BY_SOURCE_TIMESTAMP":
        return None
    if q.get("history", "").upper() != "KEEP_ALL":
        return None
    if q.get("max_samples_per_instance", "").strip() != "1":
        return None

    return ("Invalid QoS: BY_SOURCE_TIMESTAMP + KEEP_ALL + max_samples_per_instance = 1 "
            "does not provide sufficient buffer to reorder samples.\n"
            "Recommendation: increase max_samples_per_instance > 1 "
            "or switch to destination_order = BY_RECEPTION_TIMESTAMP.")
            

        
# ────────── 규칙 5 : Durability + ReaderDataLifecycle ─────────
def rule_rdlife_autopurge_vs_durability(_xml, q):
    dur_kind = q.get("durability", "").strip().upper()
    auto_delay = q.get("autopurge_disposed_samples_delay", "").strip()

    NON_VOLATILE = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}

    if dur_kind in NON_VOLATILE and auto_delay == "0":
        return ("Invalid QoS: DURABILITY.kind ≥ TRANSIENT and autopurge_disposed_samples_delay = 0.\n"
                "This setting causes DISPOSED samples to be purged immediately, "
                "negating the durability.\n"
                "Recommendation: set autopurge_disposed_samples_delay > 0 "
                "to allow late-joiners to observe disposed instances.")
    return None


 # ────────── 규칙 9 : Partition + Liveliness ─────────
def rule_liveliness_manual_partition(_xml, q):
    if q.get("liveliness", "").strip().upper() != "MANUAL_BY_TOPIC":
        return None

    part_list = q.get("partition_list", [])  # parse_profile()에서 추가 필요
    if part_list and any(p.strip() != "" for p in part_list):
        return ("Invalid QoS: LIVELINESS.kind = MANUAL_BY_TOPIC with non-empty PARTITION.\n"
                "Manual-by-topic requires the Writer to assert liveliness per partition, "
                "which may cause unexpected liveliness loss in unused partitions.\n"
                "Recommendation: use AUTOMATIC or MANUAL_BY_PARTICIPANT, or remove partition.")
    return None

 # ────────── 규칙 10 : Ownership + WriterDataLifeCycle ─────────
def rule_autodispose_with_exclusive(_xml, q):
    auto = q.get("autodispose", "").strip().upper()
    owner_kind = q.get("ownership", "").strip().upper()

    if auto == "TRUE" and owner_kind == "EXCLUSIVE":
        return ("Invalid QoS: autodispose_unregistered_instances = TRUE with EXCLUSIVE ownership.\n"
                "When the exclusive Writer unregisters, its instance is disposed immediately, "
                "preventing smooth ownership handover.\n"
                "Recommendation: set autodispose_unregistered_instances = FALSE to allow new "
                "exclusive Writers to take over without premature instance disposal.")
    return None

 # ────────── 규칙 13 : Lifespan + Durability ─────────
def rule_lifespan_too_short_for_durability(xml, q):
    dur_kind = q.get("durability", "").strip().upper()
    NON_VOLATILE = {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}

    # LIFESPAN 파싱
    lifespan_sec_match  = re.search(r"<\s*lifespan\s*>.*?<\s*sec\s*>(\d+)</sec\s*>", xml, re.I | re.S)
    lifespan_nsec_match = re.search(r"<\s*lifespan\s*>.*?<\s*nanosec\s*>(\d+)</nanosec\s*>", xml, re.I | re.S)

    if not lifespan_sec_match and not lifespan_nsec_match:
        return None

    ls_sec  = int(lifespan_sec_match.group(1)) if lifespan_sec_match else 0
    ls_nsec = int(lifespan_nsec_match.group(1)) if lifespan_nsec_match else 0
    lifespan_ns = ls_sec * 1_000_000_000 + ls_nsec

    # RTT는 전역변수로 받아옴
    RTT_NS = globals().get("rtt_ns", 50_000_000)  # 기본 50ms

    if dur_kind in NON_VOLATILE and lifespan_ns < RTT_NS:
        return (f"Invalid QoS: DURABILITY.kind = {dur_kind} with LIFESPAN duration < RTT.\n"
                f"LIFESPAN: {ls_sec}s {ls_nsec}ns ({lifespan_ns/1e6:.1f} ms) < RTT ({RTT_NS/1e6:.1f} ms).\n"
                "This setting may cause samples to expire before they are delivered to late-joiners.\n"
                "Recommendation: set lifespan ≥ RTT, or relax durability if replay is not required.")
    return None


 # ────────── 규칙 17 : Liveliness + Ownsership ─────────
def rule_exclusive_lease_infinite(xml, q):
    # 조건 1: EXCLUSIVE ownership일 때만 검사
    if q.get("ownership", "").strip().upper() != "EXCLUSIVE":
        return None

    # lease_duration 파싱
    m = LEASE_RE.search(xml)
    if not m:
        return None

    sec_raw  = m.group(1)
    nsec_raw = m.group(2)

    sec_val  = parse_duration_field(sec_raw)
    nsec_val = parse_duration_field(nsec_raw)

    # 둘 중 하나라도 무한이면 오류
    if sec_val is None or nsec_val is None:
        return ("Invalid QoS: EXCLUSIVE ownership with infinite lease_duration.\n"
                "The Writer may never be considered 'dead', preventing ownership transfer.\n"
                "Recommendation: set a finite lease_duration (e.g., 1s) to enable liveliness loss detection.")
    return None

 # ────────── 규칙 18 : Liveliness + ReaderDataLifeCycle ─────────
def rule_nowriter_delay_vs_infinite_lease(xml, q):
    # Reader 측 purge 조건
    nowriter_sec = q.get("nowriter_sec_r", "").strip()
    nowriter_nsec = q.get("nowriter_nsec_r", "").strip()

    # 파싱
    try:
        sec = int(nowriter_sec) if nowriter_sec else 0
        nsec = int(nowriter_nsec) if nowriter_nsec else 0
    except ValueError:
        return None

    purge_ns = sec * 1_000_000_000 + nsec

    if purge_ns == 0:
        return None  # purge 안 하기로 설정된 경우 → 괜찮음

    # lease_duration 파싱
    m = LEASE_RE.search(xml)
    if not m:
        return None
    sec_val = parse_duration_field(m.group(1))
    nsec_val = parse_duration_field(m.group(2))

    # lease_duration이 무한이면 purge 조건을 만족시킬 수 없음
    if sec_val is None or nsec_val is None:
        return ("Invalid QoS: Reader wants to purge samples after Writer disappearance "
                f"(autopurge_nowriter_samples_delay = {purge_ns / 1e6:.1f} ms), "
                "but liveliness lease_duration is infinite.\n"
                "→ DDS can never detect Writer loss.\n"
                "Recommendation: set a finite lease_duration to enable liveliness loss detection.")
    return None

   
 # ────────── 규칙 28 : Reliability + History ─────────
def rule_reliable_keep_last_depth_too_small(xml, q):
    if q.get("reliability", "").strip().upper() != "RELIABLE":
        return None
    if q.get("history", "").strip().upper() != "KEEP_LAST":
        return None

    # depth
    depth_txt = q.get("history_depth", "").strip()
    if not depth_txt.isdigit():
        return None
    depth = int(depth_txt)

    # publish_period_ms and rtt_ns 필요
    pub_ms = globals().get("publish_period_ms")
    rtt_ns = globals().get("rtt_ns")
    if pub_ms is None or rtt_ns is None:
        return None

    # 계산
    pp_sec = pub_ms / 1000
    rtt_sec = rtt_ns / 1_000_000_000
    required_depth = math.ceil(rtt_sec / pp_sec) + 2

    if depth < required_depth:
        return (f"Invalid QoS: RELIABLE + KEEP_LAST({depth}) is too shallow.\n"
                f"Required depth ≥ ⌈RTT / PP⌉ + 2 = ⌈{rtt_sec:.3f}s / {pp_sec:.3f}s⌉ + 2 = {required_depth}.\n"
                "Samples may be dropped before NACK retransmission is possible.\n"
                "Recommendation: increase history depth to at least this value.")
    return None

 # ────────── 규칙 29 : Reliability + Resourcelimits ─────────
def rule_keepall_max_samples_per_instance(xml, q):
    if q.get("reliability", "").strip().upper() != "RELIABLE":
        return None
    if q.get("history", "").strip().upper() != "KEEP_ALL":
        return None

    mpi_txt = q.get("max_samples_per_instance", "").strip()
    if not mpi_txt.isdigit():
        return None
    mpi = int(mpi_txt)

    # publish_period 및 rtt 필요
    pub_ms = globals().get("publish_period_ms")
    rtt_ns = globals().get("rtt_ns")
    if pub_ms is None or rtt_ns is None:
        return None

    pp_sec = pub_ms / 1000
    rtt_sec = rtt_ns / 1_000_000_000
    required_samples = math.ceil(rtt_sec / pp_sec) + 2

    if mpi < required_samples:
        return (f"Invalid QoS: RELIABLE + KEEP_ALL + max_samples_per_instance = {mpi} is too small.\n"
                f"Required ≥ ⌈RTT / PP⌉ + 2 = ⌈{rtt_sec:.3f}s / {pp_sec:.3f}s⌉ + 2 = {required_samples}.\n"
                "This setting may cause loss of samples before retransmission is completed.\n"
                "Recommendation: increase max_samples_per_instance to at least this value.")
    return None
    
 # ────────── 규칙 30 : Reliability + Lifespan ─────────
def rule_lifespan_too_short_for_reliability(xml, q):
    if q.get("reliability", "").strip().upper() != "RELIABLE":
        return None

    # lifespan 추출
    lifespan_sec_match  = re.search(r"<\s*lifespan\s*>.*?<\s*sec\s*>(\d+)</sec\s*>", xml, re.I | re.S)
    lifespan_nsec_match = re.search(r"<\s*lifespan\s*>.*?<\s*nanosec\s*>(\d+)</nanosec\s*>", xml, re.I | re.S)

    if not lifespan_sec_match and not lifespan_nsec_match:
        return None

    ls_sec  = int(lifespan_sec_match.group(1)) if lifespan_sec_match else 0
    ls_nsec = int(lifespan_nsec_match.group(1)) if lifespan_nsec_match else 0
    lifespan_ns = ls_sec * 1_000_000_000 + ls_nsec

    RTT_NS = globals().get("rtt_ns", 50_000_000)

    if lifespan_ns < RTT_NS:
        return (f"Invalid QoS: RELIABLE set but LIFESPAN duration < RTT.\n"
                f"LIFESPAN = {ls_sec}s {ls_nsec}ns = {lifespan_ns/1e6:.1f} ms < RTT = {RTT_NS/1e6:.1f} ms.\n"
                "This causes samples to expire before retransmission can occur.\n"
                "Recommendation: set lifespan ≥ RTT when using RELIABLE.")
    return None

 # ────────── 규칙 34 : Reliability + Liveliness─────────
def rule_best_effort_with_manual_liveliness(_xml, q):
    live_kind = q.get("liveliness", "").strip().upper()
    reliab = q.get("reliability", "").strip().upper()

    if live_kind == "MANUAL_BY_TOPIC" and reliab == "BEST_EFFORT":
        return ("Invalid QoS: MANUAL_BY_TOPIC liveliness requires reliable communication.\n"
                "Using BEST_EFFORT may cause liveliness assertions to be lost,\n"
                "resulting in false WRITER_NOT_ALIVE detection.\n"
                "Recommendation: use RELIABLE reliability_kind with MANUAL_BY_TOPIC liveliness.")
    return None


 # ────────── 규칙 35 : OWNERSHIP + DEADLINE ─────────
def rule_deadline_too_short_for_exclusive(xml, q):
    if q.get("ownership", "").strip().upper() != "EXCLUSIVE":
        return None
    if not deadline_enabled(xml):
        return None

    # publish_period 필요
    pub_ms = globals().get("publish_period_ms")
    if pub_ms is None:
        return None

    deadline_ns = deadline_period_ns(xml)
    if deadline_ns is None:
        return None

    pub_ns = pub_ms * 1_000_000
    min_required = 2 * pub_ns

    if deadline_ns < min_required:
        return (f"Invalid QoS: EXCLUSIVE ownership with DEADLINE period < 2×publish_period.\n"
                f"DEADLINE = {deadline_ns/1e6:.1f} ms, publish_period = {pub_ms} ms → required ≥ {2*pub_ms} ms.\n"
                "This may cause false ownership transfer due to minor publish delays.\n"
                "Recommendation: increase DEADLINE period to ≥ 2×publish_period.")
    return None
    
 # ────────── 규칙 36 : OWNERSHIP + Liveliness ─────────
def rule_lease_too_short_for_exclusive(xml, q):
    if q.get("ownership", "").strip().upper() != "EXCLUSIVE":
        return None
    if q.get("liveliness", "").strip().upper() == "":
        return None

    # publish_period 필요
    pub_ms = globals().get("publish_period_ms")
    if pub_ms is None:
        return None

    lease_ns = lease_duration_ns(xml)
    if lease_ns is None:
        return None

    pub_ns = pub_ms * 1_000_000
    required_ns = 2 * pub_ns

    if lease_ns < required_ns:
        return (f"Invalid QoS: EXCLUSIVE ownership with liveliness lease_duration < 2×publish_period.\n"
                f"lease_duration = {lease_ns/1e6:.1f} ms, publish_period = {pub_ms} ms → required ≥ {2*pub_ms} ms.\n"
                "This may cause false Writer death detection and unwanted ownership transfer.\n"
                "Recommendation: increase lease_duration to ≥ 2×publish_period.")
    return None

 # ────────── 규칙 5-1 : Durability + Resourcelimits + History ─────────
def rule_keepall_durable_instance_budget(xml, q):
    # 1. DURABILITY.kind ≥ TRANSIENT_LOCAL
    dur_kind = q.get("durability", "").strip().upper()
    if dur_kind not in {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}:
        return None

    # 2. HISTORY.kind == KEEP_ALL
    if q.get("history", "").strip().upper() != "KEEP_ALL":
        return None

    # 3. max_samples_per_instance
    mpi_txt = q.get("max_samples_per_instance", "").strip()
    if not mpi_txt.isdigit():
        return None
    mpi = int(mpi_txt)

    # 4. publish_period + rtt 필요
    pub_ms = globals().get("publish_period_ms")
    rtt_ns = globals().get("rtt_ns")
    if pub_ms is None or rtt_ns is None:
        return None

    pp_sec = pub_ms / 1000
    rtt_sec = rtt_ns / 1_000_000_000
    required = math.ceil(rtt_sec / pp_sec) + 2

    # 5. 비교
    if mpi < required:
        return (f"Invalid QoS: DURABILITY.kind = {dur_kind}, KEEP_ALL, but max_samples_per_instance = {mpi} is too small.\n"
                f"Required ≥ ⌈RTT / PP⌉ + 2 = ⌈{rtt_sec:.3f}s / {pp_sec:.3f}s⌉ + 2 = {required}.\n"
                "This may cause durable samples to be dropped before late-joiners arrive or NACKs are processed.\n"
                "Recommendation: increase max_samples_per_instance to at least this value.")
    return None
    
 # ────────── 규칙 6-1 : Durability + History ─────────
def rule_durable_keep_last_depth_1(xml, q):
    dur_kind = q.get("durability", "").strip().upper()
    hist_kind = q.get("history", "").strip().upper()

    if dur_kind not in {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}:
        return None
    if hist_kind != "KEEP_LAST":
        return None

    depth_txt = q.get("history_depth", "").strip()
    if not depth_txt.isdigit():
        return None
    depth = int(depth_txt)

    # publish_period, RTT 필요
    pub_ms = globals().get("publish_period_ms")
    rtt_ns = globals().get("rtt_ns")
    if pub_ms is None or rtt_ns is None:
        return None

    pp_sec = pub_ms / 1000
    rtt_sec = rtt_ns / 1_000_000_000
    required_depth = math.ceil(rtt_sec / pp_sec) + 2

    if depth < required_depth:
        return (f"Invalid QoS: DURABILITY.kind = {dur_kind}, KEEP_LAST({depth}) is too small.\n"
                f"Required depth ≥ ⌈RTT / PP⌉ + 2 = ⌈{rtt_sec:.3f}s / {pp_sec:.3f}s⌉ + 2 = {required_depth}.\n"
                "Durable samples may be lost before late-joiners or retransmission.\n"
                "Recommendation: increase history depth to at least this value.")
    return None

 # ────────── 규칙 14-1 : Ownership + Deadline ─────────
def rule_exclusive_deadline_infinite(xml, q):
    if q.get("ownership", "").strip().upper() != "EXCLUSIVE":
        return None

    # DEADLINE 파싱
    m = DEADLINE_RE.search(xml)
    if not m:
        return None

    sec_raw  = m.group(1)
    nsec_raw = m.group(2)

    sec_val  = parse_duration_field(sec_raw)
    nsec_val = parse_duration_field(nsec_raw)

    # 둘 중 하나라도 무한이면 문제
    if sec_val is None or nsec_val is None:
        return ("Invalid QoS: EXCLUSIVE ownership with DEADLINE = ∞.\n"
                "The system cannot detect Writer staleness, preventing ownership handover.\n"
                "Recommendation: set a finite DEADLINE period (e.g., 1s) to allow handover if Writer becomes inactive.")
    return None


 # ────────── 규칙 15-1 : Resourcelimits + Lifespan ─────────
def rule_lifespan_exceeds_per_instance(xml, q):
    # 1. KEEP_ALL 조건
    if q.get("history", "").strip().upper() != "KEEP_ALL":
        return None

    # 2. max_samples_per_instance
    mpi_txt = q.get("max_samples_per_instance", "").strip()
    if not mpi_txt.isdigit():
        return None
    mpi = int(mpi_txt)

    # 3. publish_period
    if "publish_period_ms" not in globals():
        return None
    pub_ms = globals()["publish_period_ms"]
    pp_sec = pub_ms / 1000

    # 4. lifespan
    lifespan_m_sec  = re.search(r"<\s*lifespan\s*>.*?<\s*sec\s*>(\d+)</sec\s*>", xml, re.I | re.S)
    lifespan_m_nsec = re.search(r"<\s*lifespan\s*>.*?<\s*nanosec\s*>(\d+)</nanosec\s*>", xml, re.I | re.S)
    if not lifespan_m_sec and not lifespan_m_nsec:
        return None

    ls_sec  = int(lifespan_m_sec.group(1)) if lifespan_m_sec else 0
    ls_nsec = int(lifespan_m_nsec.group(1)) if lifespan_m_nsec else 0
    lifespan_sec = ls_sec + (ls_nsec / 1_000_000_000)

    # 5. 비교
    allowed_sec = mpi * pp_sec
    if lifespan_sec > allowed_sec:
        return (f"Invalid QoS: KEEP_ALL with max_samples_per_instance = {mpi} cannot store samples for lifespan = {lifespan_sec:.3f}s.\n"
                f"Lifespan > max_samples_per_instance × publish_period = {mpi} × {pp_sec:.3f}s = {allowed_sec:.3f}s.\n"
                "This causes valid samples to be discarded early.\n"
                "Recommendation: increase max_samples_per_instance or reduce lifespan.")
    return None

 # ────────── 규칙 27-1 : Liveliness ─────────
LIVELINESS_PRIORITY = {
    "AUTOMATIC": 0,
    "MANUAL_BY_PARTICIPANT": 1,
    "MANUAL_BY_TOPIC": 2,
}

def rule_liveliness_incompatibility(pub_xml: str, sub_xml: str,
                                    pub_q: dict, sub_q: dict) -> str | None:
    # LIVENS.kind 정규화
    pub_kind = (pub_q.get("liveliness", "") or "AUTOMATIC").strip().upper()
    sub_kind = (sub_q.get("liveliness", "") or "AUTOMATIC").strip().upper()

    pub_lvl = LIVELINESS_PRIORITY.get(pub_kind, 0)
    sub_lvl = LIVELINESS_PRIORITY.get(sub_kind, 0)

    # lease_duration 추출 (ns 단위)
    pub_lease = lease_duration_ns(pub_xml)
    sub_lease = lease_duration_ns(sub_xml)

    # 두 가지 조건 중 하나라도 위반되면 경고
    msgs = []

    if pub_lvl < sub_lvl:
        msgs.append(
            f"LIVELINESS.kind mismatch: Writer='{pub_kind}' < Reader='{sub_kind}'.\n"
            "Recommendation: increase Writer's liveliness kind to match or exceed Reader's requirement."
        )

    if pub_lease is not None and sub_lease is not None:
        if pub_lease > sub_lease:
            msgs.append(
                f"LIVELINESS.lease_duration mismatch: Writer={pub_lease/1e9:.3f}s > Reader={sub_lease/1e9:.3f}s.\n"
                "Writer refreshes liveliness less frequently than Reader expects.\n"
                "Recommendation: set Writer lease_duration ≤ Reader lease_duration."
            )

    if msgs:
        return "Invalid QoS:\n" + "\n".join(msgs)

    return None


 # ────────── 규칙 5-2 : Durability + Resourcelimits + History ─────────
def rule_keepall_durable_instance_budget_1(xml, q):
    # 1. DURABILITY.kind ≥ TRANSIENT_LOCAL
    dur_kind = q.get("durability", "").strip().upper()
    if dur_kind not in {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}:
        return None

    # 2. HISTORY.kind == KEEP_ALL
    if q.get("history", "").strip().upper() != "KEEP_ALL":
        return None

    # 3. max_samples_per_instance
    mpi_txt = q.get("max_samples_per_instance", "").strip()
    if not mpi_txt.isdigit():
        return None
    mpi = int(mpi_txt)

    # 4. publish_period + rtt 필요
    pub_ms = globals().get("publish_period_ms")
    rtt_ns = globals().get("rtt_ns")
    if pub_ms is None or rtt_ns is None:
        return None

    pp_sec = pub_ms / 1000
    rtt_sec = rtt_ns / 1_000_000_000
    required = math.ceil(rtt_sec / pp_sec) + 2

    # 5. 비교
    if mpi > required:
        return (f"Invalid QoS: KEEP_ALL + DURABILITY enabled, but max_samples_per_instance = {mpi} is too large.\n"
                f"Only ⌈RTT/PP⌉+2 = ⌈{rtt_sec:.3f}/{pp_sec:.3f}⌉+2 = {required} samples needed.\n"
                "Recommendation: reduce max_samples_per_instance to save memory.")
    return None
    
 # ────────── 규칙 6-2 : Durability + History ─────────
def rule_durable_keep_last_depth_2(xml, q):
    dur_kind = q.get("durability", "").strip().upper()
    hist_kind = q.get("history", "").strip().upper()

    if dur_kind not in {"TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"}:
        return None
    if hist_kind != "KEEP_LAST":
        return None

    depth_txt = q.get("history_depth", "").strip()
    if not depth_txt.isdigit():
        return None
    depth = int(depth_txt)

    # publish_period, RTT 필요
    pub_ms = globals().get("publish_period_ms")
    rtt_ns = globals().get("rtt_ns")
    if pub_ms is None or rtt_ns is None:
        return None

    pp_sec = pub_ms / 1000
    rtt_sec = rtt_ns / 1_000_000_000
    required_depth = math.ceil(rtt_sec / pp_sec) + 2

    if depth > required_depth:
        return (f"Invalid QoS: DURABILITY={dur_kind} + KEEP_LAST({depth}) is too deep.\n"
                f"Only ⌈RTT/PP⌉+2 = ⌈{rtt_sec:.3f}/{pp_sec:.3f}⌉+2 = {required_depth} needed.\n"
                f"Recommendation: reduce history depth to ≤ {required_depth} to save memory.")
    return None
 # ────────── 규칙 14 : Lifespan + History ─────────
def rule_keep_last_lifespan_overflow(xml, q):
    if q.get("history", "").strip().upper() != "KEEP_LAST":
        return None

    depth_txt = q.get("history_depth", "").strip()
    if not depth_txt.isdigit():
        return None
    depth = int(depth_txt)

    pub_ms = globals().get("publish_period_ms")
    if pub_ms is None:
        return None
    pp_sec = pub_ms / 1000

    # lifespan 추출
    lifespan_sec_match = re.search(r"<lifespan>.*?<sec>(\d+)</sec>", xml, re.I | re.S)
    lifespan_nsec_match = re.search(r"<lifespan>.*?<nanosec>(\d+)</nanosec>", xml, re.I | re.S)
    if not lifespan_sec_match and not lifespan_nsec_match:
        return None

    ls_sec = int(lifespan_sec_match.group(1)) if lifespan_sec_match else 0
    ls_nsec = int(lifespan_nsec_match.group(1)) if lifespan_nsec_match else 0
    lifespan_sec = ls_sec + ls_nsec / 1e9

    if lifespan_sec > depth * pp_sec:
        return (f"Invalid QoS: KEEP_LAST(depth={depth}) × publish_period({pp_sec:.3f}s) "
                f"= {depth * pp_sec:.3f}s < lifespan = {lifespan_sec:.3f}s.\n"
                "Samples may be overwritten before they expire.\n"
                "Recommendation: reduce lifespan or increase history depth.")
    return None

# ────────── 규칙 ──────────
RULES = [
    (rule_durability_needs_rel, "Critical"),
    #(rule_durability_exclusive, "Warn"),
    #(rule_dstorder_requires_rel_dur, "Warn"),
    (rule_deadline_vs_durability, "Incidental"),
    #(rule_keep_last_sample_budget, "Warn"),
    #(rule_durable_keep_last_depth, "Warn"),
    #(rule_keepall_durable_unlimited, "Warn"),
    #(rule_autodispose_vs_durability, "Warn"),
    (rule_lease_vs_deadline, "Conditional"),
    #(rule_deadline_with_best_effort, "Warn"),
    (rule_exclusive_best_effort_deadline, "Conditional"),
    (rule_autodispose_with_best_effort, "Conditional"),
    (rule_lifespan_vs_deadline, "Critical"),
    #(rule_history_vs_lifespan, "Warn"),
    #(rule_exclusive_with_deadline, "Warn"),
    #(rule_buffer_capacity_vs_lifespan, "Warn"),
    (rule_dest_order_vs_depth, "Conditional"),
    #(rule_keep_last_depth_positive, "Warn"),
    (rule_history_vs_max_per_instance, "Critical"),
    #(rule_best_effort_exclusive, "Warn"),
    #(rule_announce_vs_lease, "Warn"),
    (rule_autoenable_vs_volatile_reader, "Incidental"),
    (rule_max_samples_vs_per_instance, "Critical"),
    (rule_destorder_keepall_mpi, "Conditional"),
    (rule_rdlife_autopurge_vs_durability, "Incidental"),
    (rule_liveliness_manual_partition, "Incidental"),
    (rule_autodispose_with_exclusive, "Incidental"),
    (rule_lifespan_too_short_for_durability, "Conditional"),
    (rule_exclusive_lease_infinite, "Conditional"),
    (rule_nowriter_delay_vs_infinite_lease, "Conditional"),
    (rule_reliable_keep_last_depth_too_small, "Conditional"),
    (rule_keepall_max_samples_per_instance, "Conditional"),
    (rule_lifespan_too_short_for_reliability, "Conditional"),
    (rule_best_effort_with_manual_liveliness, "Conditional"),
    (rule_deadline_too_short_for_exclusive, "Conditional"),
    (rule_lease_too_short_for_exclusive, "Conditional"),
    (rule_keepall_durable_instance_budget, "Conditional"),
    (rule_durable_keep_last_depth_1, "Conditional"),
    (rule_keepall_durable_instance_budget_1, "Conditional"),
    (rule_durable_keep_last_depth_2, "Conditional"),
    (rule_exclusive_deadline_infinite, "Conditional"),
    (rule_lifespan_exceeds_per_instance, "Conditional"),
    (rule_keep_last_lifespan_overflow, "Conditional"),


]

# ────────── 교차규칙 ──────────
CROSS_RULES = [
            (rule_dest_order_compat, "Critical"),
            (rule_ownership_compat, "Critical"),
            (rule_reliability_compat, "Critical"),
            (rule_durability_compat, "Critical"),
            (rule_deadline_period_compat, "Critical"),        # xml 2개
            #(rule_liveliness_compat, "Warn"),             # xml 2 + dict 2
            (rule_nowriter_autodispose_cross, "Conditional"),    # dict 2
            #(rule_partition_userdata_key, "Warn"),        # dict 2
            (rule_partition_overlap, "Critical"),             # ★ xml 2개
            (rule_durable_partition_miss, "Incidental"),        # xml 2 + dict 2
            (rule_deadline_partition_reset, "Incidental"),      # ★ xml 2개
            (rule_liveliness_incompatibility, "Critical"),
]

# ────────── main ──────────
SEVERITY_COLOR = {
    "Critical": "\033[31m",
    "Conditional": "\033[33m",
    "Incidental": "\033[35m",
    "Warn": "\033[37m",
    }

def main() -> None:
    # 인자: pub.xml  sub.xml  publish_period=<Nms>
    if len(sys.argv) != 5:
        sys.exit(USAGE)

    # ① XML 로드
    pub_xml = load_text(pathlib.Path(sys.argv[1]))
    sub_xml = load_text(pathlib.Path(sys.argv[2]))

    # ② publish_period=40ms → 전역 변수 publish_period_ms 저장
    _ = parse_period(sys.argv[3])           # parse_period 내부에서 globals()['publish_period_ms'] 설정
    _ = parse_rtt(sys.argv[4]) 

    # ③ XML → QoS Dict
    pub_q = parse_profile(pub_xml)          # writer 프로파일
    sub_q = parse_profile(sub_xml)          # reader 프로파일

    warnings: List[str] = []

    # ── 1) 단일-프로파일 규칙 루프 ─────────────────────────────
    for side, (xml, prof) in (("PUB", (pub_xml, pub_q)),
                              ("SUB", (sub_xml, sub_q))):
        for rule, severity in RULES:                  # RULES : (xml, prof) 형식만!
            msg = rule(xml, prof)
            if msg:
                tag=f"[{severity.upper()}]"
                color_tag = color(tag, SEVERITY_COLOR.get(severity, RED))
                warnings.append(
                    f"{color_tag} {color(f'[{side}]', BLUE)} {msg}"
                )


# ── 2) 교차-규칙 호출 ─────────────────────────────
    for rule_fn, severity in CROSS_RULES:

        if rule_fn in {
            rule_deadline_period_compat, 
            rule_partition_overlap, 
            rule_deadline_partition_reset, 
        }:
            msg = rule_fn(pub_xml, sub_xml)

        #elif rule_fn is rule_liveliness_compat:
            #msg = rule_fn(pub_xml, sub_xml, pub_q, sub_q)
            
        elif rule_fn is rule_liveliness_incompatibility: 
            msg = rule_fn(pub_xml, sub_xml, pub_q, sub_q)

        elif rule_fn is rule_durable_partition_miss:
            msg = rule_fn(pub_xml, sub_xml, pub_q, sub_q)

        else:                                   # dest_order / ownership 등
            msg = rule_fn(pub_q, sub_q)

        if msg:
            tag = f"[{severity.upper()}]"
            color_tag = color(tag, SEVERITY_COLOR.get(severity, RED))
            warnings.append(f"{color_tag} {msg}")


    # ── 3) 결과 출력 ─────────────────────────────────────────
    if warnings:
        for w in warnings:
            print(w)
        sys.exit(0)   
    print("✅  All QoS constraints satisfied.")


if __name__ == "__main__":
    main()





