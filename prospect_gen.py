"""
Prospect generation engine.
Creates randomized players aged 14-17 each offseason who age into the draft pool.
"""
import random
import math

# ─────────────────────────────────────────────────────────────────────────────
# Name pools by nationality
# ─────────────────────────────────────────────────────────────────────────────
NAMES = {
    "Canadian": {
        "first_m": ["Connor", "Nathan", "Cole", "Brady", "Tyler", "Ryan", "Jordan",
                    "Jake", "Dylan", "Owen", "Mason", "Logan", "Hunter", "Carter",
                    "Braden", "Kyle", "Brett", "Cam", "Ethan", "Lucas", "Noah",
                    "Matthew", "Aidan", "Colton", "Wyatt", "Liam", "Evan", "Justin",
                    "Derek", "Travis", "Cody", "Adam", "Jason", "Kevin", "Scott",
                    "Brendan", "Riley", "Austin", "Nolan", "Dillon", "Zack", "Sean"],
        "last":   ["Smith", "Johnson", "Williams", "Brown", "Jones", "Wilson",
                   "Taylor", "Anderson", "Martin", "Thompson", "White", "Harris",
                   "Clark", "Lewis", "Robinson", "Walker", "Hall", "Young", "King",
                   "Scott", "Green", "Baker", "Adams", "Mitchell", "Campbell",
                   "Murray", "MacDonald", "Robertson", "Stewart", "Ross", "Morrison",
                   "Fraser", "Reid", "MacKenzie", "Ferguson", "Patterson", "Hamilton",
                   "Gallagher", "Leblanc", "Tremblay", "Gagnon", "Roy", "Bouchard",
                   "Côté", "Fortin", "Gagné", "Picard", "Lavoie", "Beaulieu"],
    },
    "American": {
        "first_m": ["Jack", "Luke", "Max", "Sam", "Ben", "Zach", "Will", "Alex",
                    "Nick", "Josh", "Tyler", "Kyle", "Drew", "Chase", "Blake",
                    "Brock", "Reed", "Grant", "Tanner", "Spencer", "Hunter",
                    "Parker", "Garrett", "Dalton", "Cade", "Tate", "Brett",
                    "Cole", "Troy", "Quinn", "Landon", "Jackson", "Cooper",
                    "Logan", "Mason", "Wyatt", "Dylan", "Caleb", "Evan", "Seth"],
        "last":   ["Miller", "Davis", "Garcia", "Martinez", "Nelson", "Carter",
                   "Mitchell", "Perez", "Roberts", "Turner", "Phillips", "Campbell",
                   "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris",
                   "Rogers", "Reed", "Cook", "Morgan", "Bell", "Murphy", "Bailey",
                   "Cooper", "Richardson", "Cox", "Howard", "Ward", "Torres",
                   "Peterson", "Gray", "Ramirez", "James", "Watson", "Brooks",
                   "Kelly", "Sanders", "Price", "Bennett", "Wood", "Barnes"],
    },
    "Swedish": {
        "first_m": ["Viktor", "Emil", "Elias", "Gustav", "Oscar", "Anton", "Erik",
                    "Filip", "Linus", "Mattias", "Rickard", "Jonas", "Henrik",
                    "Marcus", "Sebastian", "Pontus", "Oliver", "William", "Hugo",
                    "Axel", "Isak", "Albin", "Arvid", "Edvin", "Fabian", "Joakim",
                    "Carl", "Lars", "Nils", "Stefan", "Tobias", "Mikael", "Johan",
                    "Peter", "Adam", "Andreas", "Patrik", "Simon", "Viggo", "Ivar"],
        "last":   ["Karlsson", "Lindstrom", "Pettersson", "Andersson", "Nilsson",
                   "Eriksson", "Larsson", "Olsson", "Persson", "Svensson",
                   "Gustafsson", "Johansson", "Magnusson", "Jonsson", "Hansson",
                   "Franzen", "Hedman", "Backstrom", "Forsberg", "Lundqvist",
                   "Landeskog", "Ekman-Larsson", "Hoglander", "Brannstrom",
                   "Holmstrom", "Sundin", "Alfredsson", "Naslund", "Lidstrom",
                   "Borje", "Bjork", "Stenberg", "Command", "Soderstrom"],
    },
    "Finnish": {
        "first_m": ["Mikko", "Jukka", "Pekka", "Teemu", "Saku", "Ville", "Jari",
                    "Olli", "Esa", "Aleksi", "Iiro", "Jussi", "Toni", "Joonas",
                    "Kaapo", "Patrik", "Rasmus", "Aatu", "Eeli", "Joakim",
                    "Roope", "Jesse", "Valtteri", "Matias", "Kasper", "Juuso",
                    "Niko", "Sampo", "Henri", "Eetu", "Noel", "Antti", "Tuukka",
                    "Markus", "Lauri", "Miro", "Otto", "Samu", "Luka"],
        "last":   ["Koivu", "Selanne", "Lehtinen", "Ruutu", "Numminen", "Turris",
                   "Laine", "Aho", "Barkov", "Vatanen", "Makinen", "Pakarinen",
                   "Virtanen", "Niskanen", "Jokinen", "Hemsky", "Immonen",
                   "Tolvanen", "Puljujarvi", "Maatta", "Soini", "Pesonen",
                   "Kakko", "Heiskanen", "Hietanen", "Kotkansalo", "Alalauri",
                   "Arkko", "Nousiainen", "Mantyla", "Lepisto", "Aalto"],
    },
    "Russian": {
        "first_m": ["Alexander", "Nikita", "Andrei", "Evgeni", "Ivan", "Mikhail",
                    "Dmitri", "Sergei", "Pavel", "Ilya", "Kirill", "Matvei",
                    "Artem", "Maxim", "Roman", "Vitali", "Vladislav", "Denis",
                    "Alexei", "Nikolai", "Igor", "Anton", "Semyon", "Vadim",
                    "Ruslan", "Yegor", "Danil", "Stepan", "Gleb", "Timur"],
        "last":   ["Ovechkin", "Malkin", "Kucherov", "Panarin", "Tarasenko",
                   "Shipachyov", "Voronkov", "Michkov", "Gusev", "Marchenko",
                   "Svechnikov", "Orlov", "Nesterov", "Zaitsev", "Provorov",
                   "Telegin", "Lyubimov", "Shirokov", "Yakupov", "Grigorenko",
                   "Bobrov", "Kovalev", "Fedorov", "Datsyuk", "Zetterberg",
                   "Khusnutdinov", "Yurov", "Miftakhov", "Afanasyev", "Ivanov"],
    },
    "Czech": {
        "first_m": ["David", "Jakub", "Ondrej", "Tomas", "Martin", "Radim",
                    "Lukas", "Filip", "Jan", "Michal", "Pavel", "Roman",
                    "Petr", "Jiri", "Adam", "Marek", "Dominik", "Vojtech",
                    "Stanislav", "Zbynek", "Radek", "Jaroslav", "Libor"],
        "last":   ["Pastrnak", "Voracek", "Plekanec", "Hamrlik", "Jagr",
                   "Hasek", "Nedved", "Hejduk", "Satan", "Streit",
                   "Novak", "Dvorak", "Horak", "Kratochvil", "Blazejewski",
                   "Chytil", "Zohorna", "Cervenka", "Smid", "Kubes",
                   "Cerny", "Krejci", "Spacek", "Vidensky", "Malek"],
    },
    "German": {
        "first_m": ["Leon", "Moritz", "Lukas", "Dominik", "Tobias", "Florian",
                    "Markus", "Thomas", "Stefan", "Michael", "Simon", "Felix",
                    "Maximilian", "Alexander", "Johannes", "Christian", "Andreas"],
        "last":   ["Draisaitl", "Seider", "Kahun", "Peterka", "Stützle",
                   "Niederreiter", "Grubauer", "Reimer", "Ullmark", "Wolf",
                   "Müller", "Schmidt", "Schneider", "Fischer", "Wagner",
                   "Bauer", "Richter", "Hoffmann", "Koch", "Schäfer"],
    },
    "Swiss": {
        "first_m": ["Nico", "Jonas", "Luca", "Kevin", "Raphael", "Nino",
                    "Damien", "Reto", "Yannick", "Gaetan", "Timo", "Marco"],
        "last":   ["Hischier", "Fiala", "Meier", "Josi", "Niederreiter",
                   "Kukan", "Genoni", "Untersander", "Bertschy", "Rohrbach",
                   "Aeschlimann", "Herzog", "Diaz", "Berra", "Moser"],
    },
    "Latvian": {
        "first_m": ["Zemgus", "Roderick", "Kristaps", "Ralfs", "Rihards",
                    "Teodors", "Gints", "Martins", "Janis", "Miks"],
        "last":   ["Girgensons", "Balcers", "Kulda", "Kenins", "Berzins",
                   "Daugavins", "Sics", "Abols", "Zile", "Zvejnieks"],
    },
    "Slovak": {
        "first_m": ["Tomas", "Martin", "Juraj", "Roman", "Marian", "Peter",
                    "Michal", "Rastislav", "Robert", "Pavol", "Milan"],
        "last":   ["Tatar", "Hossa", "Gaborik", "Chara", "Halak",
                   "Slafkovsky", "Nemec", "Svozil", "Chromiak", "Regenda"],
    },
}

# Junior / developmental leagues by nationality
LEAGUES = {
    "Canadian":  [("OHL", ["Brantford Bulldogs","London Knights","Windsor Spitfires",
                            "Kingston Frontenacs","Ottawa 67's","Mississauga Steelheads",
                            "Oshawa Generals","Kitchener Rangers","Sudbury Wolves",
                            "Barrie Colts","Sault Ste. Marie Greyhounds"]),
                  ("WHL", ["Portland Winterhawks","Seattle Thunderbirds","Everett Silvertips",
                            "Vancouver Giants","Victoria Royals","Kelowna Rockets",
                            "Prince George Cougars","Calgary Hitmen","Lethbridge Hurricanes",
                            "Moose Jaw Warriors","Regina Pats","Swift Current Broncos",
                            "Saskatoon Blades","Brandon Wheat Kings","Winnipeg Ice",
                            "Red Deer Rebels","Medicine Hat Tigers","Edmonton Oil Kings"]),
                  ("QMJHL",["Rimouski Océanic","Chicoutimi Saguenéens","Sherbrooke Phoenix",
                              "Rouyn-Noranda Huskies","Shawinigan Cataractes",
                              "Drummondville Voltigeurs","Baie-Comeau Drakkar",
                              "Cape Breton Eagles","Halifax Mooseheads",
                              "Moncton Wildcats","Saint John Sea Dogs"])],
    "American":  [("USHL", ["Chicago Steel","Waterloo Black Hawks","Des Moines Buccaneers",
                              "Tri-City Storm","Sioux City Musketeers","Madison Capitols",
                              "Green Bay Gamblers","Muskegon Lumberjacks","Dubuque Fighting Saints",
                              "Omaha Lancers","Sioux Falls Stampede","Fargo Force"]),
                  ("NCAA", ["Michigan Wolverines","Boston University Terriers",
                             "Minnesota Golden Gophers","North Dakota Fighting Hawks",
                             "Denver Pioneers","Penn State Nittany Lions",
                             "Boston College Eagles","Wisconsin Badgers",
                             "Notre Dame Fighting Irish","Quinnipiac Bobcats"])],
    "Swedish":   [("SHL",      ["Frolunda HC","Djurgardens IF","Skelleftea AIK",
                                 "Leksands IF","Modo Hockey","HV71","Orebro HK",
                                 "Linkoping HC","Lulea HF","Vaxjo Lakers"]),
                  ("J20 SuperElit",["Frolunda J20","Djurgardens J20","Skelleftea J20",
                                    "Leksands IF Jr.","Farjestad BK J20","Orebro HK Jr.",
                                    "Brynäs J20","Modo J20"])],
    "Finnish":   [("Liiga",    ["TPS Turku","HIFK Helsinki","Kärpät Oulu","JYP Jyväskylä",
                                 "Tappara Tampere","Ilves Tampere","Pelicans Lahti",
                                 "Ässät Pori","KooKoo Kouvola","HPK Hämeenlinna"]),
                  ("Liiga Jr.",["TPS Jr.","HIFK Jr.","Kärpät Jr.","JYP Jr.",
                                "Tappara Jr.","Pelicans Lahti U20","HPK Jr."])],
    "Russian":   [("KHL",      ["CSKA Moscow","SKA St. Petersburg","Ak Bars Kazan",
                                 "Metallurg Magnitogorsk","Dinamo Moscow","Lokomotiv Yaroslavl",
                                 "Avangard Omsk","Salavat Yulaev Ufa"]),
                  ("MHL",      ["CSKA Krasnaya Armiya","SKA-1946","Reaktor Nizhnekamsk",
                                 "Kapitan Stupino","Dynamo-Shinnik"])],
    "Czech":     [("Extraliga", ["HC Oceláři Třinec","HC Pardubice","HC Kometa Brno",
                                  "HC Sparta Praha","HC Olomouc","HC Vítkovice Steel"]),
                  ("Czech Jr.", ["HC Sparta Praha Jr.","HC Pardubice Jr.","HC Třinec Jr."])],
    "German":    [("DEL",       ["Red Bull München","Adler Mannheim","EHC Biel",
                                  "Kölner Haie","Eisbären Berlin","Nürnberg Ice Tigers"])],
    "Swiss":     [("NL",        ["ZSC Lions","Lausanne HC","HC Lugano","HC Davos",
                                  "SC Bern","Genève-Servette HC","Langnau SCL Tigers"])],
    "Latvian":   [("Extraliga", ["Dinamo Riga","HK Riga 2000"])],
    "Slovak":    [("Tipsport",  ["HK Dukla Trenčín","HC Slovan Bratislava",
                                  "HC Košice","HC 05 Banská Bystrica"])],
}

# Nationality distribution for random generation
NATIONALITY_WEIGHTS = {
    "Canadian": 32, "American": 24, "Swedish": 14, "Finnish": 10,
    "Russian": 8, "Czech": 5, "German": 3, "Swiss": 2,
    "Latvian": 1, "Slovak": 1,
}

# Position distribution
POSITIONS = ["C", "LW", "RW", "D", "D", "G"]
POSITION_WEIGHTS = [18, 17, 17, 28, 0, 10]   # D appears twice in list; G=10%

ARCHETYPES = {
    "C":  ["Playmaker", "Two-Way Center", "Sniper", "Faceoff Specialist", "Power Forward"],
    "LW": ["Power Forward", "Sniper", "Grinder", "Playmaker", "Pest"],
    "RW": ["Sniper", "Power Forward", "Playmaker", "Speedster", "Grinder"],
    "D":  ["Puck-Mover", "Stay-at-Home", "Two-Way Defender", "Offensive Defender", "Enforcer"],
    "G":  ["Butterfly", "Hybrid", "Stand-Up", "Athletic"],
}

SCOUT_GRADES = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D"]


def weighted_choice(options, weights):
    total = sum(weights)
    r = random.uniform(0, total)
    upto = 0
    for opt, w in zip(options, weights):
        upto += w
        if upto >= r:
            return opt
    return options[-1]


def get_name(nationality):
    pool = NAMES.get(nationality, NAMES["Canadian"])
    first = random.choice(pool["first_m"])
    last  = random.choice(pool["last"])
    return first, last


def get_league_and_team(nationality, age):
    league_options = LEAGUES.get(nationality, LEAGUES["Canadian"])
    league_name, teams = random.choice(league_options)
    team = random.choice(teams)
    return team, league_name


def generate_ratings(position, potential, age_at_generation):
    """
    Generate attribute ratings for a prospect.
    Current ratings are well below potential, based on age.
    Older prospects (17) are closer to their potential than younger (14).
    """
    # How far along their development (0.0 = just starting, 1.0 = peaked)
    dev_factor = (age_at_generation - 14) / 8.0  # 14→0.0, 18→0.5, 22→1.0
    dev_factor = max(0.1, min(0.6, dev_factor))   # clamp for prospects

    def attr(weight=1.0, variance=8):
        base = potential * weight * dev_factor
        base = max(35, min(potential, base + random.gauss(0, variance)))
        return int(round(base))

    if position == "G":
        return {
            "reflexes":      attr(1.0),
            "positioning":   attr(0.95),
            "rebound_ctrl":  attr(0.90),
            "puck_handling": attr(0.80),
            "skating": 0, "shooting": 0, "passing": 0,
            "defense": 0, "physical": 0, "puck_control": 0, "awareness": 0,
        }

    profile = {
        "C":  {"skating":0.85,"shooting":0.90,"passing":1.00,"defense":0.80,
               "physical":0.70,"puck_control":0.95,"awareness":0.90},
        "LW": {"skating":0.90,"shooting":1.00,"passing":0.80,"defense":0.70,
               "physical":0.90,"puck_control":0.90,"awareness":0.80},
        "RW": {"skating":0.90,"shooting":1.00,"passing":0.80,"defense":0.70,
               "physical":0.85,"puck_control":0.90,"awareness":0.80},
        "D":  {"skating":0.85,"shooting":0.70,"passing":0.85,"defense":1.00,
               "physical":1.00,"puck_control":0.80,"awareness":0.95},
    }.get(position, {"skating":0.85,"shooting":0.85,"passing":0.85,"defense":0.85,
                     "physical":0.85,"puck_control":0.85,"awareness":0.85})

    ratings = {k: attr(v) for k, v in profile.items()}
    ratings.update({"reflexes":0,"positioning":0,"rebound_ctrl":0,"puck_handling":0})
    return ratings


def potential_to_scout_grade(potential):
    """Convert hidden potential OVR to a scout grade letter."""
    if potential >= 93:   return "A+"
    elif potential >= 89: return "A"
    elif potential >= 85: return "A-"
    elif potential >= 81: return "B+"
    elif potential >= 77: return "B"
    elif potential >= 73: return "B-"
    elif potential >= 69: return "C+"
    elif potential >= 65: return "C"
    elif potential >= 61: return "C-"
    else:                 return "D"


def generate_potential():
    """
    Most prospects are average (C range). Elite prospects are rare.
    Distribution designed so ~5% are A-tier, ~20% B-tier, ~50% C-tier, ~25% D-tier.
    """
    roll = random.random()
    if roll < 0.02:   return random.randint(93, 99)   # franchise player
    elif roll < 0.07: return random.randint(88, 92)   # star
    elif roll < 0.20: return random.randint(82, 87)   # top-6 / top-4
    elif roll < 0.45: return random.randint(76, 81)   # solid NHLer
    elif roll < 0.70: return random.randint(70, 75)   # depth / bubble
    elif roll < 0.88: return random.randint(63, 69)   # AHL regular
    else:             return random.randint(50, 62)   # bust


def generate_cohort(season_year, count_per_age=None):
    """
    Generate a fresh cohort of prospects for the given season year.
    Creates players aged 14-17 (birth years season_year-17 through season_year-14).
    They will age into draft eligibility at 18.
    """
    if count_per_age is None:
        count_per_age = {14: 30, 15: 28, 16: 26, 17: 24}  # ~108 new prospects/yr

    nationalities = list(NATIONALITY_WEIGHTS.keys())
    nat_weights   = list(NATIONALITY_WEIGHTS.values())
    positions     = ["C", "LW", "RW", "D", "G"]
    pos_weights   = [18, 17, 17, 38, 10]

    prospects = []
    for age, count in count_per_age.items():
        birth_year = season_year - age
        for _ in range(count):
            nationality = weighted_choice(nationalities, nat_weights)
            position    = weighted_choice(positions, pos_weights)
            first, last = get_name(nationality)
            team, league = get_league_and_team(nationality, age)
            potential   = generate_potential()
            ratings     = generate_ratings(position, potential, age)
            archetype   = random.choice(ARCHETYPES.get(position, ["Two-Way"]))
            shoots      = random.choice(["L", "L", "L", "R", "R"])

            p = {
                "first_name":    first,
                "last_name":     last,
                "position":      position,
                "birth_year":    birth_year,
                "nationality":   nationality,
                "shoots":        shoots,
                "archetype":     archetype,
                "current_team":  team,
                "current_league": league,
                "potential":     potential,
                "scout_grade":   potential_to_scout_grade(potential),
                "draft_year":    birth_year + 18,  # eligible year they turn 18
                **ratings,
            }
            prospects.append(p)

    random.shuffle(prospects)
    return prospects


def develop_prospect(p_data, seasons=1):
    """
    Age a prospect by N seasons, moving their current ratings toward potential.
    Progress is faster early, slower as they approach ceiling. Some busts.
    Returns updated ratings dict.
    """
    potential = p_data["potential"]
    bust_factor = random.gauss(1.0, 0.15)  # 0.85–1.15 multiplier per player
    bust_factor = max(0.6, min(1.05, bust_factor))

    def develop_attr(current, weight=1.0):
        effective_pot = int(potential * weight * bust_factor)
        gap = effective_pot - current
        if gap <= 0:
            return max(current - random.randint(0, 1), 1)  # tiny regression possible
        # Bigger gains when farther from ceiling
        gain = random.gauss(gap * 0.15, 3.0) * seasons
        return int(min(effective_pot, current + max(0, gain)))

    attrs = ["skating","shooting","passing","defense","physical","puck_control","awareness",
             "reflexes","positioning","rebound_ctrl","puck_handling"]
    weights = {
        "C":  [0.85,0.90,1.00,0.80,0.70,0.95,0.90,0,0,0,0],
        "LW": [0.90,1.00,0.80,0.70,0.90,0.90,0.80,0,0,0,0],
        "RW": [0.90,1.00,0.80,0.70,0.85,0.90,0.80,0,0,0,0],
        "D":  [0.85,0.70,0.85,1.00,1.00,0.80,0.95,0,0,0,0],
        "G":  [0,0,0,0,0,0,0,1.0,0.95,0.90,0.80],
    }.get(p_data.get("position","C"), [0.85]*7+[0]*4)

    updated = dict(p_data)
    for attr, w in zip(attrs, weights):
        if w > 0 and p_data.get(attr, 0) > 0:
            updated[attr] = develop_attr(p_data[attr], w)

    return updated
