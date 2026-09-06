MAX_AUDIO_BYTES = 5 * 1024 * 1024
MIN_DURATION_S = 1.0
MAX_DURATION_S = 60.0
AUDIO_TTL_HOURS = 24
AUDIO_ID_PREFIX = "rec_"
MAX_ASR_ENCODED_BYTES = 10 * 1024 * 1024
ASR_TIMEOUT_S = 20.0
EXTRACT_TIMEOUT_S = 15.0
EXTRACT_MAX_TOKENS = 1024
DEFAULT_CATEGORY = "咖啡店"
VAGUE_ADDRESSES = frozenset({"我家", "家里", "公司", "单位"})
SEARCH_ID_PREFIX = "srch_"
SEARCH_TTL_HOURS = 24
AMAP_CALL_TIMEOUT_S = 5.0
SEARCH_TOTAL_TIMEOUT_S = 25.0
AROUND_RADIUS_FIRST_M = 2000
AROUND_RADIUS_EXPAND_M = 5000
MAX_POIS = 3
SAME_PLACE_MAX_M = 80.0
CHINA_LON_RANGE = (73.0, 135.0)
CHINA_LAT_RANGE = (3.0, 54.0)
LEVEL_ACCEPT = frozenset(
    {"兴趣点", "公交地铁站点", "门牌号", "门址", "道路交叉路口", "住宅区", "单元号"}
)
LEVEL_REJECT = frozenset(
    {"国家", "省", "市", "区县", "开发区", "乡镇", "村庄", "道路", "未知", "热点商圈"}
)
LEVEL_PRIORITY = {
    "门牌号": 0,
    "门址": 1,
    "兴趣点": 2,
    "公交地铁站点": 3,
    "道路交叉路口": 4,
    "住宅区": 5,
    "单元号": 6,
}
TTS_ID_PREFIX = "tts_"
TTS_TTL_HOURS = 24
REPLY_TIMEOUT_S = 15.0
TTS_TIMEOUT_S = 15.0
TTS_DOWNLOAD_TIMEOUT_S = 8.0
FINALIZE_TOTAL_TIMEOUT_S = 42.0
REPLY_MAX_TOKENS = 256
PUBLIC_BASE_URL = "http://localhost:8003"
