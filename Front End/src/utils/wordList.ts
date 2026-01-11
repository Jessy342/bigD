// Words categorized by difficulty level
const EASY_WORDS = [
  'HELLO', 'WORLD', 'HAPPY', 'SMILE', 'LIGHT',
  'MUSIC', 'HEART', 'PEACE', 'DANCE', 'SWEET',
  'WATER', 'EARTH', 'BREAD', 'HOUSE', 'CHAIR',
  'TABLE', 'PHONE', 'PAPER', 'PARTY', 'BEACH',
  'CLOUD', 'GRASS', 'PLANT', 'FRUIT', 'SUNNY',
  'GREEN', 'BLACK', 'WHITE', 'BROWN', 'COLOR',
];

const MEDIUM_WORDS = [
  'REACT', 'BUILD', 'CRAFT', 'PIXEL', 'QUEST',
  'SCALE', 'STACK', 'DEBUG', 'MERGE', 'PARSE',
  'CLONE', 'LOGIC', 'ARRAY', 'ASYNC', 'CACHE',
  'CLASS', 'EVENT', 'FIBER', 'GRAPH', 'HOOKS',
  'INDEX', 'LAYER', 'MIXIN', 'NODES', 'PATCH',
  'QUERY', 'REDUX', 'SCOPE', 'TOKEN', 'TYPES',
  'VALUE', 'WATCH', 'YIELD', 'ZONES', 'BOARD',
  'CHAOS', 'EQUAL', 'FOCUS', 'GRACE', 'IMAGE',
  'JOLLY', 'KNIFE', 'MAGIC', 'NIGHT', 'OCEAN',
  'QUICK', 'RIVER', 'SHINE', 'TIGER', 'UNITY',
  'VOICE', 'YOUTH', 'ZEBRA', 'SUPER', 'ROYAL',
];

const HARD_WORDS = [
  'ABYSS', 'BLITZ', 'JAZZY', 'FUZZY', 'FIZZY',
  'QUIRK', 'DWARF', 'GLYPH', 'LYMPH', 'NYMPH',
  'SYNTH', 'WRYLY', 'THYME', 'WHISK', 'BRISK',
  'CRISP', 'FLASK', 'FLANK', 'GRIND', 'GRUMP',
  'TRUMP', 'PLUMB', 'SHRUG', 'SHRUB', 'SKULK',
  'SLUNK', 'DRUNK', 'CHUNK', 'PLUNK', 'FLUNK',
  'SWUNG', 'SLUNG', 'CLUNG', 'WRUNG', 'FLUNG',
  'SPUNK', 'TRUNK', 'SKUNK', 'STUNK', 'CRUMB',
  'THUMB', 'NUMB', 'DUMB', 'QUALM', 'PSALM',
  'BALMY', 'CALMS', 'PALMS', 'REALM', 'QUALM',
];

const EXPERT_WORDS = [
  'AXION', 'BUFFS', 'CYNIC', 'DRYLY', 'EPOXY',
  'FJORD', 'GLYPH', 'HAIKU', 'INBOX', 'JIFFY',
  'KAZOO', 'LUXES', 'MYRRH', 'NIXED', 'ONYX',
  'PROXY', 'QUAFF', 'RAZZED', 'SCHWA', 'TOPAZ',
  'UNZIP', 'VIXEN', 'WALTZ', 'XEROX', 'YUCKY',
  'ZESTY', 'AFFIX', 'BUZZY', 'CADDY', 'DIZZY',
  'EXXON', 'FRIZZ', 'GIZMO', 'HAZY', 'INDIE',
  'JAZZY', 'KLUTZ', 'LYMPH', 'MIXED', 'NIXIE',
  'OOMPH', 'PIXIE', 'QUACK', 'RAZZ', 'SWIZZ',
];

// Combine all words for validation
export const WORD_LIST = [...EASY_WORDS, ...MEDIUM_WORDS, ...HARD_WORDS, ...EXPERT_WORDS];

// Valid words that can be guessed (includes word list + common words)
export const VALID_WORDS = new Set([
  ...WORD_LIST,
  'ABOUT', 'ABOVE', 'ABUSE', 'ACTOR', 'ACUTE',
  'ADMIT', 'ADOPT', 'ADULT', 'AFTER', 'AGAIN',
  'AGENT', 'AGREE', 'AHEAD', 'ALARM', 'ALBUM',
  'ALERT', 'ALIEN', 'ALIGN', 'ALIKE', 'ALIVE',
  'ALLOW', 'ALONE', 'ALONG', 'ALTER', 'AMBER',
  'AMONG', 'ANGEL', 'ANGER', 'ANGLE', 'ANGRY',
  'APART', 'APPLE', 'APPLY', 'ARENA', 'ARGUE',
  'ARISE', 'ASIDE', 'ASSET', 'AUDIO', 'AVOID',
  'AWAKE', 'AWARD', 'AWARE', 'BADLY', 'BAKER',
  'BEACH', 'BEAST', 'BLACK', 'BLADE', 'BLAME',
  'BLANK', 'BLAST', 'BLEED', 'BLESS', 'BLIND',
  'BLOCK', 'BLOOD', 'BLOOM', 'BLOWN', 'BOOTH',
  'BOUND', 'BRAIN', 'BRAND', 'BRAKE', 'BRAVE', 'BREAD',
  'BREAK', 'BREED', 'BRIEF', 'BRING', 'BROAD',
  'BROKE', 'BROWN', 'BUYER', 'CABLE', 'CARRY',
  'CATCH', 'CAUSE', 'CHAIN', 'CHAIR', 'CHART',
  'CHASE', 'CHEAP', 'CHECK', 'CHEST', 'CHIEF',
  'CHILD', 'CHINA', 'CHOSE', 'CIVIL', 'CLAIM',
  'CLEAN', 'CLEAR', 'CLICK', 'CLIMB', 'CLOCK',
  'CLOSE', 'CLOUD', 'COACH', 'COAST', 'COULD',
  'COUNT', 'COURT', 'COVER', 'CRACK', 'CRASH',
  'CRAZY', 'CREAM', 'CRIME', 'CROSS', 'CROWD',
  'CROWN', 'CRUDE', 'CURVE', 'CYCLE', 'DAILY',
  'DEALT', 'DEATH', 'DELAY', 'DELTA', 'DENSE',
  'DEPTH', 'DOING', 'DOUBT', 'DOZEN', 'DRAFT',
  'DRAIN', 'DRAMA', 'DRANK', 'DRAWN', 'DREAM',
  'DRESS', 'DRIFT', 'DRILL', 'DRINK', 'DRIVE',
  'DROVE', 'DYING', 'EAGER', 'EARLY', 'EARTH',
  'EIGHT', 'ELITE', 'EMPTY', 'ENEMY', 'ENJOY',
  'ENTER', 'ENTRY', 'ERROR', 'EXACT', 'EXIST',
  'EXTRA', 'FAITH', 'FALSE', 'FAULT', 'FIBER',
  'FIELD', 'FIFTH', 'FIFTY', 'FIGHT', 'FINAL',
  'FIRST', 'FIXED', 'FLASH', 'FLEET', 'FLOOR',
  'FLUID', 'FORTH', 'FORTY', 'FORUM', 'FOUND',
  'FRAME', 'FRANK', 'FRAUD', 'FRESH', 'FRONT',
  'FRUIT', 'FULLY', 'FUNNY', 'GIANT', 'GIVEN',
  'GLASS', 'GLOBE', 'GOING', 'GRACE', 'GRADE',
  'GRAIN', 'GRAND', 'GRANT', 'GRASS', 'GRAVE',
  'GREAT', 'GREEN', 'GROSS', 'GROUP', 'GROWN',
  'GUARD', 'GUESS', 'GUEST', 'GUIDE', 'HAPPY',
  'HARRY', 'HEART', 'HEAVY', 'HENCE', 'HENRY',
  'HORSE', 'HOTEL', 'HOUSE', 'HUMAN', 'IDEAL',
  'INNER', 'INPUT', 'ISSUE', 'JAPAN', 'JONES',
  'JUDGE', 'KNOWN', 'LABEL', 'LARGE', 'LASER',
  'LATER', 'LAUGH', 'LAYER', 'LEARN', 'LEASE',
  'LEAST', 'LEAVE', 'LEGAL', 'LEMON', 'LEVEL',
  'LEWIS', 'LIGHT', 'LIMIT', 'LINKS', 'LIVES',
  'LOCAL', 'LOGIC', 'LOOSE', 'LOWER', 'LUCKY',
  'LUNCH', 'LYING', 'MAGIC', 'MAJOR', 'MAKER',
  'MARCH', 'MARIA', 'MATCH', 'MAYBE', 'MAYOR',
  'MEANT', 'MEDIA', 'METAL', 'MIGHT', 'MINOR',
  'MINUS', 'MIXED', 'MODEL', 'MONEY', 'MONTH',
  'MORAL', 'MOTOR', 'MOUNT', 'MOUSE', 'MOUTH',
  'MOVED', 'MOVIE', 'MUSIC', 'NEEDS', 'NEVER',
  'NEWLY', 'NIGHT', 'NOISE', 'NORTH', 'NOTED',
  'NOVEL', 'NURSE', 'OCCUR', 'OCEAN', 'OFFER',
  'OFTEN', 'ORDER', 'OTHER', 'OUGHT', 'PAINT',
  'PANEL', 'PAPER', 'PARTY', 'PEACE', 'PETER',
  'PHASE', 'PHONE', 'PHOTO', 'PIECE', 'PILOT',
  'PITCH', 'PLACE', 'PLAIN', 'PLANE', 'PLANT',
  'PLATE', 'POINT', 'POUND', 'POWER', 'PRESS',
  'PRICE', 'PRIDE', 'PRIME', 'PRINT', 'PRIOR',
  'PRIZE', 'PROOF', 'PROUD', 'PROVE', 'QUEEN',
  'QUICK', 'QUIET', 'QUITE', 'RADIO', 'RAISE',
  'RANGE', 'RAPID', 'RATIO', 'REACH', 'READY',
  'REFER', 'RIGHT', 'RIVAL', 'RIVER', 'ROMAN',
  'ROUGH', 'ROUND', 'ROUTE', 'ROYAL', 'RURAL',
  'SCALE', 'SCENE', 'SCOPE', 'SCORE', 'SENSE',
  'SERVE', 'SEVEN', 'SHALL', 'SHAPE', 'SHARE',
  'SHARP', 'SHEET', 'SHELF', 'SHELL', 'SHIFT',
  'SHINE', 'SHIRT', 'SHOCK', 'SHOOT', 'SHORT',
  'SHOWN', 'SIGHT', 'SINCE', 'SIXTH', 'SIXTY',
  'SIZED', 'SKILL', 'SLEEP', 'SLIDE', 'SMALL',
  'SMART', 'SMILE', 'SMITH', 'SMOKE', 'SOLID',
  'SOLVE', 'SORRY', 'SOUND', 'SOUTH', 'SPACE',
  'SPARE', 'SPEAK', 'SPEED', 'SPEND', 'SPENT',
  'SPLIT', 'SPOKE', 'SPORT', 'STAFF', 'STAGE',
  'STAKE', 'STAND', 'START', 'STATE', 'STEAM',
  'STEEL', 'STICK', 'STILL', 'STOCK', 'STONE',
  'STOOD', 'STORE', 'STORM', 'STORY', 'STRIP',
  'STUCK', 'STUDY', 'STUFF', 'STYLE', 'SUGAR',
  'SUITE', 'SUNNY', 'SUPER', 'SWEET', 'TABLE',
  'TAKEN', 'TASTE', 'TAXES', 'TEACH', 'TERRY',
  'TEXAS', 'THANK', 'THEFT', 'THEIR', 'THEME',
  'THERE', 'THESE', 'THICK', 'THING', 'THINK',
  'THIRD', 'THOSE', 'THREE', 'THREW', 'THROW',
  'TIGHT', 'TIMES', 'TITLE', 'TODAY', 'TOPIC',
  'TOTAL', 'TOUCH', 'TOUGH', 'TOWER', 'TRACK',
  'TRADE', 'TRAIN', 'TREAT', 'TREND', 'TRIAL',
  'TRIBE', 'TRIED', 'TRIES', 'TRUCK', 'TRULY',
  'TRUST', 'TRUTH', 'TWICE', 'UNDER', 'UNDUE',
  'UNION', 'UNITY', 'UNTIL', 'UPPER', 'UPSET',
  'URBAN', 'USAGE', 'USUAL', 'VALID', 'VALUE',
  'VIDEO', 'VIRUS', 'VISIT', 'VITAL', 'VOCAL',
  'VOTER', 'WASTE', 'WATCH', 'WATER', 'WHEEL',
  'WHERE', 'WHICH', 'WHILE', 'WHITE', 'WHOLE',
  'WHOSE', 'WOMAN', 'WOMEN', 'WORLD', 'WORRY',
  'WORSE', 'WORST', 'WORTH', 'WOULD', 'WOUND',
  'WRITE', 'WRONG', 'WROTE', 'YOUNG', 'YOUTH',
]);

export function getRandomWord(level: number = 1): string {
  // Determine difficulty based on level
  let wordPool: string[];
  
  if (level === 1) {
    // Level 1: Easy only
    wordPool = EASY_WORDS;
  } else if (level <= 5) {
    // Levels 2-5: Mix of easy and medium, increasing medium proportion
    const mediumRatio = (level - 1) / 4; // 0.25, 0.5, 0.75, 1.0
    if (Math.random() < mediumRatio) {
      wordPool = MEDIUM_WORDS;
    } else {
      wordPool = EASY_WORDS;
    }
  } else if (level <= 10) {
    // Levels 6-10: Mix of medium and hard
    const hardRatio = (level - 5) / 5; // 0.2, 0.4, 0.6, 0.8, 1.0
    if (Math.random() < hardRatio) {
      wordPool = HARD_WORDS;
    } else {
      wordPool = MEDIUM_WORDS;
    }
  } else if (level <= 20) {
    // Levels 11-20: Mix of hard and expert
    const expertRatio = (level - 10) / 10; // 0.1, 0.2, ..., 1.0
    if (Math.random() < expertRatio) {
      wordPool = EXPERT_WORDS;
    } else {
      wordPool = HARD_WORDS;
    }
  } else {
    // Level 20+: Expert words only
    wordPool = EXPERT_WORDS;
  }
  
  return wordPool[Math.floor(Math.random() * wordPool.length)];
}

export function isValidWord(word: string): boolean {
  return VALID_WORDS.has(word.toUpperCase());
}
