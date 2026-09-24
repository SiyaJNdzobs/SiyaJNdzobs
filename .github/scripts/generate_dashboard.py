import os
import json
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime

USERNAME = os.environ["GITHUB_USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]

API = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "github-profile-dashboard"
}


def github_get(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())


def graphql(query):
    data = json.dumps({"query": query}).encode()

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=data,
        headers={
            **HEADERS,
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode())

    if "errors" in result:
        raise RuntimeError(result["errors"])

    return result["data"]


# ---------------------------------------------------------
# CONTRIBUTIONS
# ---------------------------------------------------------

graphql_query = f"""
{{
  user(login: "{USERNAME}") {{

    contributionsCollection {{

      totalCommitContributions

      totalPullRequestContributions

      totalPullRequestReviewContributions

      totalIssueContributions

      totalRepositoryContributions

      contributionCalendar {{
        totalContributions
        weeks {{
          contributionDays {{
            date
            contributionCount
          }}
        }}
      }}
    }}

    repositories(
      first: 100
      ownerAffiliations: OWNER
      privacy: PUBLIC
    ) {{
      nodes {{
        name

        languages(
          first: 10
          orderBy: {{field: SIZE, direction: DESC}}
        ) {{
          edges {{
            size
            node {{
              name
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""

data = graphql(graphql_query)
user = data["user"]
contributions = user["contributionsCollection"]


commits = contributions["totalCommitContributions"]
pull_requests = contributions["totalPullRequestContributions"]
reviews = contributions["totalPullRequestReviewContributions"]
issues = contributions["totalIssueContributions"]
repositories_created = contributions["totalRepositoryContributions"]

total_contributions = contributions["contributionCalendar"]["totalContributions"]


# ---------------------------------------------------------
# CONTRIBUTION CALENDAR
# ---------------------------------------------------------

days = []

for week in contributions["contributionCalendar"]["weeks"]:
    for day in week["contributionDays"]:
        days.append(day)

days.sort(key=lambda x: x["date"])

last_30 = days[-30:]

max_day = max(
    [day["contributionCount"] for day in last_30],
    default=1
)


# ---------------------------------------------------------
# LANGUAGES
# ---------------------------------------------------------

language_bytes = defaultdict(int)

for repository in user["repositories"]["nodes"]:

    if not repository:
        continue

    languages = repository.get("languages")

    if not languages:
        continue

    for edge in languages["edges"]:
        language = edge["node"]["name"]
        size = edge["size"]

        language_bytes[language] += size


total_language_bytes = sum(language_bytes.values())

languages = []

if total_language_bytes:

    for language, size in sorted(
        language_bytes.items(),
        key=lambda item: item[1],
        reverse=True
    ):

        percentage = (size / total_language_bytes) * 100

        languages.append(
            (language, percentage)
        )


languages = languages[:6]


# ---------------------------------------------------------
# RECENT GITHUB ACTIVITY
# ---------------------------------------------------------

events = github_get(
    f"{API}/users/{USERNAME}/events/public?per_page=30"
)

recent_activity = []

for event in events:

    event_type = event.get("type")
    payload = event.get("payload", {})
    repo = event.get("repo", {}).get("name", "")

    created = event.get("created_at", "")

    try:
        date = datetime.fromisoformat(
            created.replace("Z", "+00:00")
        ).strftime("%d %b %Y")
    except Exception:
        date = "Recent"

    text = None

    if event_type == "PushEvent":

        commits_count = len(
            payload.get("commits", [])
        )

        text = (
            f" Pushed {commits_count} "
            f"commit(s) to {repo}"
        )

    elif event_type == "PullRequestEvent":

        action = payload.get("action", "updated")

        text = (
            f"🔀 {action.capitalize()} "
            f"pull request in {repo}"
        )

    elif event_type == "PullRequestReviewEvent":

        action = payload.get("action", "submitted")

        text = (
            f" {action.capitalize()} "
            f"a code review in {repo}"
        )

    elif event_type == "IssuesEvent":

        action = payload.get("action", "updated")

        text = (
            f"🐛 {action.capitalize()} "
            f"an issue in {repo}"
        )

    elif event_type == "CreateEvent":

        ref_type = payload.get(
            "ref_type",
            "repository"
        )

        text = (
            f" Created {ref_type} "
            f"in {repo}"
        )

    elif event_type == "ForkEvent":

        text = f"🍴 Forked {repo}"

    if text:

        recent_activity.append(
            (text, date)
        )

    if len(recent_activity) >= 5:
        break


# ---------------------------------------------------------
# LANGUAGE BARS
# ---------------------------------------------------------

language_rows = ""

for language, percentage in languages:

    bar_length = int(
        min(percentage, 100) / 5
    )

    bar = "█" * bar_length
    empty = "░" * (20 - bar_length)

    language_rows += f"""
    <text x="600" y="{205 + len(language_rows.splitlines()) * 0}" 
          class="language">
      {language}
    </text>
    """


# Build language section properly
language_svg = ""

start_y = 205

for index, (language, percentage) in enumerate(languages):

    y = start_y + index * 35

    filled = int(
        (percentage / 100) * 220
    )

    language_svg += f"""
    <text x="600" y="{y}" class="language">
      {language}
    </text>

    <rect
      x="700"
      y="{y - 13}"
      width="220"
      height="12"
      rx="6"
      fill="#1f2937"
    />

    <rect
      x="700"
      y="{y - 13}"
      width="{filled}"
      height="12"
      rx="6"
      fill="#58a6ff"
    />

    <text
      x="940"
      y="{y}"
      class="percentage"
    >
      {percentage:.1f}%
    </text>
    """


# ---------------------------------------------------------
# RECENT ACTIVITY SECTION
# ---------------------------------------------------------

activity_svg = ""

start_y = 475

for index, (activity, date) in enumerate(
    recent_activity
):

    y = start_y + index * 38

    activity_svg += f"""
    <text x="55" y="{y}" class="activity">
      {activity[:75]}
    </text>

    <text x="900" y="{y}" class="date">
      {date}
    </text>
    """


if not recent_activity:

    activity_svg = """
    <text x="55" y="475" class="activity">
      No recent public activity found.
    </text>
    """


# ---------------------------------------------------------
# CONTRIBUTION HEATMAP
# ---------------------------------------------------------

heatmap_svg = ""

heatmap_start_x = 55
heatmap_start_y = 325

for index, day in enumerate(last_30):

    column = index % 15
    row = index // 15

    x = heatmap_start_x + column * 32
    y = heatmap_start_y + row * 25

    count = day["contributionCount"]

    if count == 0:
        fill = "#161b22"
    elif count <= 2:
        fill = "#0e4429"
    elif count <= 5:
        fill = "#006d32"
    elif count <= 10:
        fill = "#26a641"
    else:
        fill = "#39d353"

    heatmap_svg += f"""
    <rect
      x="{x}"
      y="{y}"
      width="20"
      height="20"
      rx="4"
      fill="{fill}"
    />
    """


# ---------------------------------------------------------
# DASHBOARD SVG
# ---------------------------------------------------------

svg = f"""<svg
xmlns="http://www.w3.org/2000/svg"
width="1000"
height="760"
viewBox="0 0 1000 760">

<defs>

<style>

.title {{
    font-family: Arial, sans-serif;
    font-size: 26px;
    font-weight: bold;
    fill: #f0f6fc;
}}

.subtitle {{
    font-family: Arial, sans-serif;
    font-size: 13px;
    fill: #8b949e;
}}

.number {{
    font-family: Arial, sans-serif;
    font-size: 26px;
    font-weight: bold;
    fill: #58a6ff;
}}

.label {{
    font-family: Arial, sans-serif;
    font-size: 12px;
    fill: #8b949e;
}}

.language {{
    font-family: Arial, sans-serif;
    font-size: 14px;
    fill: #c9d1d9;
}}

.percentage {{
    font-family: Arial, sans-serif;
    font-size: 13px;
    fill: #8b949e;
}}

.activity {{
    font-family: Arial, sans-serif;
    font-size: 13px;
    fill: #c9d1d9;
}}

.date {{
    font-family: Arial, sans-serif;
    font-size: 12px;
    fill: #8b949e;
}}

</style>

</defs>


<!-- BACKGROUND -->

<rect
width="1000"
height="760"
rx="18"
fill="#0d1117"
stroke="#30363d"
/>


<!-- HEADER -->

<text
x="50"
y="55"
class="title">

 GitHub Activity Dashboard

</text>

<text
x="50"
y="80"
class="subtitle">

@{USERNAME} • Automatically updated by GitHub Actions

</text>


<!-- STAT CARDS -->

<rect
x="50"
y="110"
width="165"
height="90"
rx="12"
fill="#161b22"
stroke="#30363d"
/>

<text x="70" y="145" class="number">
{total_contributions}
</text>

<text x="70" y="170" class="label">
Contributions
</text>


<rect
x="230"
y="110"
width="165"
height="90"
rx="12"
fill="#161b22"
stroke="#30363d"
/>

<text x="250" y="145" class="number">
{commits}
</text>

<text x="250" y="170" class="label">
Commits
</text>


<rect
x="410"
y="110"
width="165"
height="90"
rx="12"
fill="#161b22"
stroke="#30363d"
/>

<text x="430" y="145" class="number">
{pull_requests}
</text>

<text x="430" y="170" class="label">
Pull Requests
</text>


<rect
x="590"
y="110"
width="165"
height="90"
rx="12"
fill="#161b22"
stroke="#30363d"
/>

<text x="610" y="145" class="number">
{reviews}
</text>

<text x="610" y="170" class="label">
Code Reviews
</text>


<rect
x="770"
y="110"
width="165"
height="90"
rx="12"
fill="#161b22"
stroke="#30363d"
/>

<text x="790" y="145" class="number">
{issues}
</text>

<text x="790" y="170" class="label">
Issues
</text>


<!-- CONTRIBUTION ACTIVITY -->

<text
x="55"
y="240"
class="title"
font-size="20">

Contribution Activity

</text>

{heatmap_svg}


<!-- LANGUAGES -->

<text
x="600"
y="370"
class="title"
font-size="20">

Languages

</text>

{language_svg}


<!-- RECENT ACTIVITY -->

<text
x="55"
y="445"
class="title"
font-size="20">

Recent Activity

</text>

{activity_svg}


<!-- FOOTER -->

<text
x="55"
y="730"
class="subtitle">

Updated automatically • GitHub API • Public activity

</text>

</svg>
"""


# ---------------------------------------------------------
# SAVE
# ---------------------------------------------------------

os.makedirs(
    "assets",
    exist_ok=True
)

with open(
    "assets/github-dashboard.svg",
    "w",
    encoding="utf-8"
) as file:

    file.write(svg)

print("GitHub dashboard generated successfully.")
