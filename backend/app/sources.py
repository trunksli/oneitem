"""
Where ONE looks. Edit freely -- ingestion reads everything from here.

Chosen for the incrementality thesis: obsessive experts, small publications, and
work people are unlikely to meet in their feeds anyway. Every source below was
fetched and parsed successfully on 10 September 2026. Feeds that failed then
(Low-tech Magazine, Dirt, Core77) are left out rather than retried every run.

Costs per pipeline run (four a day), at most:
  YouTube   3 quota units per channel (of 10,000 a day)
  Articles  one page fetch per new item
  Vimeo     one oEmbed request per new film
  Podcasts  nothing beyond the feed itself -- the audio is never downloaded
"""

# How many NEW items each source may add per run. Keeps one prolific feed from
# flooding the pool, and bounds the page fetches and scoring each run pays for.
NEW_ITEMS_PER_FEED = 3
NEW_VIDEOS_PER_CHANNEL = 3

# Shorts and trailers are not what ONE is for.
MIN_VIDEO_SECONDS = 120

# Articles and essays (RSS/Atom).
ARTICLE_FEEDS = [
    # Science and ideas
    "https://www.quantamagazine.org/feed/",
    "https://aeon.co/feed.rss",
    "https://nautil.us/feed/",
    "https://psyche.co/feed",
    "https://www.noemamag.com/feed/",
    "https://knowablemagazine.org/rss",
    "https://hakaimagazine.com/feed/",
    "https://www.smithsonianmag.com/rss/latest_articles/",
    # Oddities and history
    "https://www.atlasobscura.com/feeds/latest",
    "https://publicdomainreview.org/rss.xml",
    "https://www.damninteresting.com/feed/",
    "https://www.messynessychic.com/feed/",
    "https://languagelog.ldc.upenn.edu/nll/?feed=rss2",
    # Culture, art and design
    "https://www.themarginalian.org/feed/",
    "https://www.openculture.com/feed",
    "https://www.theparisreview.org/blog/feed/",
    "https://www.thisiscolossal.com/feed/",
    "https://hyperallergic.com/feed/",
    "https://www.bldgblog.com/feed/",
    # Long reads, music, food, sport
    "https://longreads.com/feed/",
    "https://thequietus.com/feed",
    "https://aquariumdrunkard.com/feed/",
    "https://www.eater.com/rss/index.xml",
    "https://defector.com/feed",
    # Short films, written up
    "https://www.shortoftheweek.com/feed/",
]

# Films. Embedded with Vimeo's do-not-track player.
VIMEO_FEEDS = [
    "https://vimeo.com/channels/staffpicks/videos/rss",
]

# Podcasts. Played from the publisher's own audio host.
PODCAST_FEEDS = [
    "https://feeds.simplecast.com/BqbsxVfO",                       # 99% Invisible
    "https://feed.articlesofinterest.club/",                       # Articles of Interest
    "https://feed.songexploder.net/SongExploder",                  # Song Exploder
    "https://feeds.megaphone.fm/switchedonpop",                    # Switched on Pop
    "https://feed.20k.org",                                        # Twenty Thousand Hertz
    "http://feeds.thememorypalace.us/thememorypalace",             # The Memory Palace
    "https://feeds.megaphone.fm/VMP7924981569",                    # Criminal
    "https://feeds.simplecast.com/EmVW7VGp",                       # Radiolab
    "https://feeds.acast.com/public/shows/696572d375c092ac4e159c27",  # Decoder Ring
    "https://feeds.megaphone.fm/elt-spot",                         # Every Little Thing
    "https://feeds.megaphone.fm/SLT4637136223",                    # Lexicon Valley
    "https://feeds.simplecast.com/FO6kxYGj",                       # Ologies
]

# YouTube channel ids (resolved from handles once, so runs never spend quota on it).
YOUTUBE_CHANNELS = {
    # Engineering and making
    "UCMOqf8ab-42UUQIdVoKwjlQ": "Practical Engineering",
    "UCy0tKL1T7wFoYcxCe0xjN6Q": "Technology Connections",
    "UClRwC5Vc8HrB6vGx6Ti-lhA": "Technology Connextras",
    "UCivA7_KLKWo43tFcCkFvydw": "Applied Science",
    "UC06HVrkOL33D5lLnCPjr6NQ": "Breaking Taps",
    "UCworsKCR-Sx6R6-BnIjS2MA": "Clickspring",
    "UC3bosUr3WlKYm4sBaLs-Adw": "CuriousMarc",
    "UCILl8ozWuxnFYXIe2svjHhg": "BPS.space",
    "UCvZe6ZCbF9xgbbbdkiodPKQ": "Baumgartner Restoration",
    # Science and maths
    "UCDprHm6lgtPo9hrEmocZwwg": "AlphaPhoenix",
    "UCSju5G2aFaWMqn-_0YBtq5A": "Stand-up Maths",
    "UC52kszkc08-acFOuogFl5jw": "Tibees",
    "UCtESv1e7ntJaLJYKIO1FoYw": "Periodic Videos",
    "UCvBqzzvUBLCs8Y7Axb-jZew": "Sixty Symbols",
    "UCtwKon9qMt5YLVgQt1tvJKg": "Objectivity",
    "UC1D3yD4wlPMico0dss264XA": "NileBlue",
    "UCeiYXex_fwgYDonaTcSIk6w": "MinuteEarth",
    "UCSl5Uxu2LyaoAoMMGp6oTJA": "Atomic Shrimp",
    # History, places and systems
    "UC1LpsuAUaKoMzzJSEt5WImw": "Asianometry",
    "UC4sEmXUuWIFlxRIFBRV6VXQ": "The History Guy",
    "UCVo63lbKHjC04KqYhwSZ_Pg": "Defunctland",
    "UC0intLFzLaudFG-xAvUEO-A": "Not Just Bikes",
    "UCgNg3vwj3xt7QOrcIDaHdFg": "PolyMatter",
    "UC9RM-iSvTu1uPJb8X5yp3EQ": "Wendover Productions",
    "UCuCkxoKLYO_EQ2GeFtbM_bw": "Half as Interesting",
    "UCMk_WSPy3EE16aK5HLzCJzw": "NativLang",
    # Food
    "UCsaGKqPZnGp_7N80hcHySGQ": "Tasting History",
    "UC54SLBnD5k5U3Q6N__UjbAw": "Chinese Cooking Demystified",
    # Music, film and games
    "UCnkp4xDOwqqJD7sSM3xdUiQ": "Adam Neely",
    "UCeZLO2VgbZHeDcongKzzfOw": "8-bit Music Theory",
    "UCz2iUx-Imr6HgDC3zAFpjOw": "David Bennett Music Theory",
    "UCJkMlOu7faDgqh4PfzbpLdg": "Nerdwriter1",
    "UCeTfBygNb1TahcNpZyELO8g": "Jacob Geller",
    "UCUNoEsSfUcyNlaJbieYkMvg": "Jon Bois",
}
