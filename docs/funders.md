# The funder registry: where the Prospector starts

The [prospector](https://github.com/hallettmiket/murmurent/blob/main/agents/prospector.md)
finds the funding opportunities a person may apply for and reports each one
from the funder's own page. This file is where it starts: the agencies
people in this country apply to most, each with the page that lists its
competitions, what that page gives, how it loads, and the date it was last
checked. The [bookworm](https://github.com/hallettmiket/murmurent/blob/main/agents/bookworm.md)
keeps it, as it keeps the EDID resources and the reporting checklists; the
prospector proposes entries and never edits the file.

**What an entry is and is not.** An entry says that an agency exists, which
page lists its competitions, and what that page showed on the date checked.
It is not an opportunity. The prospector opens the page on the day it is
asked, because deadlines move every year and programs are renamed, merged
and closed: two of the best-known Canadian programs were found closed on the
day this file was made (below). A reader who wants the current competition
opens the page, not this file.

**Tiers.** The prospector reads them in this order, nearest first:

1. **The institution's own competitions** are not in this file. They live
   in the institution pack, `institution/<unique_name>/funding.yaml`
   ([the institution pack](institution_pack.md)): the internal awards, the
   research office's screened lists, and the research office's **internal
   deadline rule**, which the prospector reports beside every external
   deadline. A pack without that file makes the tier `Unknown`. The example
   pack ships one with invented facts.
2. **The province or state.**
3. **The country.**
4. **The disease or field.** The common ones are here; the rest the
   prospector finds per request and proposes.
5. **International**: competitions open to applicants from this country.

The entries below are Canadian, Ontarian and the main US, European and
international funders, because that is where this centre is. Another
centre's bookworm replaces the country and province tiers with its own and
keeps the shape.

## How each page loads

The **Loads** column is the honest part of this file. Many funders now put
their listings behind a script that a plain page fetch does not run, and
some refuse automated fetches outright. The prospector must know which
before it reports `UNRESOLVED` for the wrong reason.

| Loads | Meaning | What the prospector does |
|---|---|---|
| plain | the listing and its dates come through a plain fetch | read it |
| script | the page loads but its listing is drawn by a script; a plain fetch shows the frame and no rows | open it in a browser, or use the feed in the next column, or report `SECONDARY` from a page that does come through |
| refused | the site answers 403, a certificate error, or a block page to a plain fetch | use the feed if one exists; else `UNRESOLVED: the site refuses automated reading`, with the link for the person |

**Feed** names a machine-readable source (RSS, JSON, a documented API) that
was loaded on the date checked. A feed is what a scheduled poller would read;
none is used for anything yet.

## Canada

| Agency | Listing page | What it gave on the date checked | Loads | Feed | Funds | Checked |
|---|---|---|---|---|---|---|
| CIHR (Canadian Institutes of Health Research) | <https://cihr-irsc.gc.ca/e/37788.html> | the funding overview; the competitions themselves are in ResearchNet, <https://www.researchnet-recherchenet.ca/rnr16/search.do?fodAgency=CIHR&fodLanguage=E&all=1&search=true&org=CIHR&sort=program&masterList=true&view=currentOpps>, which a plain fetch could not load (certificate error) | overview plain; ResearchNet refused | none found | health research: operating grants, fellowships, doctoral awards, team grants | 2026-11-12 |
| NSERC (Natural Sciences and Engineering Research Council) | <https://nserc-crsng.canada.ca/en/funding-opportunity> | every program by name with a "date modified", no deadlines on the list page; each program's page carries its own | plain | none found | natural sciences and engineering: Discovery, Alliance, scholarships and fellowships | 2026-11-12 |
| SSHRC (Social Sciences and Humanities Research Council) | <https://sshrc-crsh.canada.ca/en/funding/opportunities.aspx> | an opportunities table with a Deadline column, drawn by script | script | none found | social sciences and humanities | 2026-11-12 |
| New Frontiers in Research Fund (NFRF) | <https://sshrc-crsh.canada.ca/funding-financement/nfrf-fnfr/index-eng.aspx> | the competitions by name; each competition page carries its dates (the 2026 Exploration page gave a notice of intent on 2026-08-18 and a full application on 2026-10-20) | plain | none found | interdisciplinary, high-risk research, all three agencies | 2026-11-12 |
| Canada Foundation for Innovation (CFI) | <https://www.innovation.ca/apply-manage-awards/funding-opportunities> | the funds by name with descriptions; each fund's page carries its competitions and deadlines | plain | none found | research infrastructure and equipment | 2026-11-12 |
| Mitacs | <https://www.mitacs.ca/our-programs/> | the programs by name, no deadlines (most take applications through the year) | plain | <https://www.mitacs.ca/feed/> (site news, not opportunities) | internships and fellowships with partners, Accelerate, Elevate, Globalink | 2026-11-12 |
| Genome Canada | <https://genomecanada.ca/funding-opportunities/> | an opportunities listing drawn by script | script | none found | genomics and its applications | 2026-11-12 |
| Canada Research Chairs | <https://www.chairs-chaires.gc.ca/program-programme/nomination-mise_en_candidature-eng.aspx> | the nomination process; nominations are continuous and made by the institution | plain | <https://www.chairs-chaires.gc.ca/rss-eng.xml> (news) | chairs, through the institution | 2026-11-12 |
| Canada Postdoctoral Research Award | <https://www.nserc-crsng.gc.ca/Students-Etudiants/PD-NP/cpra-bprc_eng.asp> (named by the Banting page; not yet read) | the Banting Postdoctoral Fellowships page, <https://banting.fellowships-bourses.gc.ca/en/home-accueil.html>, says that program is closed and points here | Banting page plain | none found | postdoctoral fellowships across the three agencies | 2026-11-12 |
| Canada Graduate Research Scholarship, Doctoral | <https://nserc-crsng.canada.ca/en/funding-opportunity/canada-graduate-research-scholarship-doctoral-program> | the program with its deadline (October 17, 8:00 pm ET for direct applicants; institutions set earlier internal dates). The Vanier page, <https://vanier.gc.ca/en/home-accueil.html>, says Vanier is closed and replaced by this | plain | none found | doctoral students | 2026-11-12 |
| Canada Graduate Research Scholarship, Master's | <https://nserc-crsng.canada.ca/en/funding-opportunity/canada-graduate-research-scholarship-masters-program> | the program with its deadline (December 1, 8:00 pm ET, annually) | plain | none found | master's students | 2026-11-12 |

## Ontario

| Agency | Listing page | What it gave on the date checked | Loads | Feed | Funds | Checked |
|---|---|---|---|---|---|---|
| Early Researcher Awards | <https://www.ontario.ca/page/early-researcher-awards> | the program; said the current round's deadline had passed and gave no dates | plain | none found | early-career researchers at Ontario institutions | 2026-11-12 |
| Ontario Research Fund | <https://www.ontario.ca/page/ontario-research-fund> | Research Excellence and Research Infrastructure described, no rounds or dates | plain | none for opportunities | research excellence and infrastructure in Ontario | 2026-11-12 |
| Ontario Institute for Cancer Research (OICR) | <https://oicr.on.ca/funding-opportunities/> | three active 2026 opportunities named, no dates on the list page | plain | none found | cancer research in Ontario | 2026-11-12 |
| Ontario Graduate Scholarship (OGS) | not found: the provincial pages tried returned "not found"; institutions publish their own OGS pages, so the institution tier is where to look | | | | master's and doctoral students at Ontario institutions | 2026-11-12 |

## Disease and field charities, Canada

| Agency | Listing page | What it gave on the date checked | Loads | Feed | Funds | Checked |
|---|---|---|---|---|---|---|
| Brain Canada | <https://braincanada.ca/research/funding-opportunities> | opportunities with deadlines | plain | email alerts only | brain and nervous system research | 2026-11-12 |
| Canadian Cancer Society | <https://cancer.ca/en/research/for-researchers/funding-opportunities> | opportunities with deadlines | plain | none found | cancer research, all stages | 2026-11-12 |
| Terry Fox Research Institute | <https://www.tfri.ca/funding-opportunities> | programs described, no deadlines on the list page | plain | none found | cancer research, team programs | 2026-11-12 |
| Heart and Stroke Foundation | <https://www.heartandstroke.ca/what-we-do/research/for-researchers> | opportunities with deadlines | plain | none found | cardiovascular and stroke research, personnel awards | 2026-11-12 |
| Cystic Fibrosis Canada | <https://www.cysticfibrosis.ca/our-programs/research/funding-opportunities> | opportunities with deadlines | plain | none found | cystic fibrosis research, fellowships, seed grants | 2026-11-12 |
| Alzheimer Society of Canada | <https://alzheimer.ca/en/research/information-researchers/alzheimer-society-research-program> | the program; the call was paused for a strategic review | plain | none found | dementia research | 2026-11-12 |
| Crohn's and Colitis Canada | <https://crohnsandcolitis.ca/research/apply-for-funding> | programs described; the 2026 competition closed, no dates | plain | none found | inflammatory bowel disease research | 2026-11-12 |
| Diabetes Canada | <https://www.diabetes.ca/research/funding-opportunities> | programs described; the 2026 awards closed, no open deadlines | plain | none found | diabetes research | 2026-11-12 |
| Breakthrough T1D Canada (formerly JDRF) | <https://breakthrought1d.ca/research/grant-opportunities/> | opportunities with deadlines | plain | none found | type 1 diabetes research | 2026-11-12 |
| Kidney Foundation of Canada | <https://kidney.ca/Research/Funding-Opportunities> | programs described; a competition subpage returned "not found" | plain | none found | kidney research | 2026-11-12 |
| Parkinson Canada | <https://parkinson.ca/research/apply-for-funding/> | opportunities with deadlines | plain | none found | Parkinson's research | 2026-11-12 |
| MS Canada | <https://mscanada.ca/about-us/information-for-researchers> | programs described, competitions marked closed, no dates | plain | none found | multiple sclerosis research | 2026-11-12 |
| Arthritis Society Canada | <https://arthritis.ca/researchers/research-programs-awards/> | opportunities with deadlines | plain | mailing list only | arthritis research, fellowships | 2026-11-12 |

## United States

| Agency | Listing page | What it gave on the date checked | Loads | Feed | Funds | Checked |
|---|---|---|---|---|---|---|
| NIH Guide for Grants and Contracts | <https://grants.nih.gov/funding/searchguide/> | the Guide, its weekly index and its RSS page all answered 403 to a plain fetch | refused | the Guide publishes RSS feeds, on a page that itself refused | biomedical research; many programs admit foreign institutions, each notice says | 2026-11-12 |
| NSF (National Science Foundation) | <https://www.nsf.gov/funding/opportunities> | the opportunities search is drawn by script; the RSS page <https://www.nsf.gov/rss> came through | script | <https://www.nsf.gov/rss/rss_www_funding_pgm_annc_inf.xml> (program announcements) and <https://www.nsf.gov/rss/rss_www_funding_upcoming.xml> (upcoming due dates; loaded, items carry deadlines) | science and engineering; foreign applicants only through a US partner, each solicitation says | 2026-11-12 |
| Grants.gov | <https://www.grants.gov/search-grants> | the search is drawn by script | script | RSS at <https://www.grants.gov/connect/rss-feeds> (new and modified opportunities by agency and category); API at <https://www.grants.gov/api> with search and fetch endpoints documented at <https://www.grants.gov/api/applicant/> | every US federal grant notice | 2026-11-12 |
| DoD CDMRP (Congressionally Directed Medical Research Programs) | <https://cdmrp.health.mil/funding/default> | one open program named, no deadlines; the program announcements page answered 403 | plain, announcements refused | none found | disease-specific programs (cancer, neuroscience, and others); foreign institutions admitted, each announcement says | 2026-11-12 |
| Gates Foundation | <https://www.gatesfoundation.org/about/how-we-work/grant-opportunities> | links to its submission portal and Grand Challenges; no opportunities on the page | plain | none found | global health and development, through Grand Challenges calls | 2026-11-12 |
| Chan Zuckerberg Initiative | <https://chanzuckerberg.com/grants-ventures/grants/> | a grant database showing no open calls on the date checked | plain | none found | science programs by call | 2026-11-12 |
| Simons Foundation | <https://www.simonsfoundation.org/funding-opportunities/> | opportunities with deadlines | plain | <https://www.simonsfoundation.org/feed/> (site-wide) | mathematics, physical sciences, life sciences, autism research | 2026-11-12 |
| Alzheimer's Association | <https://www.alz.org/research/for_researchers/grants> | the program; said the current cycle was open and pointed to a how-to-apply page for the dates | plain | none found | dementia research, international | 2026-11-12 |

## Europe and international

| Agency | Listing page | What it gave on the date checked | Loads | Feed | Funds | Checked |
|---|---|---|---|---|---|---|
| EU Funding and Tenders portal (Horizon Europe) | <https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals> | the portal is drawn by script; only its title came through | script | a bulk file of calls at <https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData/grantsTenders.json> (too large for a plain fetch) and a search API that answers POST at <https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA> | Horizon Europe calls; Canada is an associated country, each call says who may apply | 2026-11-12 |
| European Research Council (ERC) | <https://erc.europa.eu/apply-grant> | the schemes described, no call dates on the page | plain | none found | frontier research grants at every career stage, hosted in Europe | 2026-11-12 |
| Human Frontier Science Program (HFSP) | <https://www.hfsp.org/funding/hfsp-funding/research-grants> | the call with its timeline (letter of intent in March, full proposals in September); the funding index page answered 403 | plain, index refused | none found | international collaborative life-science research grants and fellowships | 2026-11-12 |
| Wellcome | <https://wellcome.org/grant-funding/schemes> | a scheme list sortable by deadline, drawn by script | script | none found | discovery research, mental health, climate and health, infectious disease; international | 2026-11-12 |
| EMBO | <https://www.embo.org/funding/fellowships-grants-and-career-support/> | programs by name; the postdoctoral fellowships page gave its next deadline (2027-01-22, 14:00 CET) | plain | none found | life-science fellowships and grants, international | 2026-11-12 |
| Cancer Research UK | <https://find.cancerresearchuk.org/funding-schemes> | a scheme finder drawn by script | script | none found | cancer research; some schemes open to non-UK applicants, each says | 2026-11-12 |
| Michael J. Fox Foundation | <https://www.michaeljfox.org/funding-opportunities> | opportunities with deadlines | plain | email alerts only | Parkinson's research, international | 2026-11-12 |

## Closed or renamed, found on the date checked

Programs a person may still ask for by their old name. The prospector
answers with the replacement and the page that says so.

| Asked for | What the page said on 2026-11-12 | Page |
|---|---|---|
| Banting Postdoctoral Fellowships | closed; replaced by the Canada Postdoctoral Research Award | <https://banting.fellowships-bourses.gc.ca/en/home-accueil.html> |
| Vanier Canada Graduate Scholarships | closed; replaced by the Canada Graduate Research Scholarship, Doctoral | <https://vanier.gc.ca/en/home-accueil.html> |
| Canada Graduate Scholarships (CGS-M, CGS-D) | renamed Canada Graduate Research Scholarship | the two program pages in the Canada table |
| JDRF Canada | renamed Breakthrough T1D | <https://breakthrought1d.ca/research/grant-opportunities/> |

## For the bookworm: the backlog

What the first pass could not settle, to be read and entered.

- **The CIHR ResearchNet database** is the one listing that matters most for
  health research here and refused a plain fetch (certificate error). Read
  it in a browser, record what it lists and whether any feed exists.
- **The NIH Guide** refused every page. Its RSS feeds exist; find a route
  that loads one and record its address.
- **The Ontario Graduate Scholarship**: no provincial page was found. Each
  institution publishes its own; the institution tier is where it belongs.
- **The Canada Postdoctoral Research Award** page, named by the Banting
  page, has not been read yet.
- **The script-rendered listings** (SSHRC, Genome Canada, NSF, Grants.gov,
  the EU portal, Wellcome, Cancer Research UK): find for each the plain page
  or the feed that gives the rows, and record it in the Feed column.
- **A disease or field the registry lacks** that a request turns up and that
  funds that subject every year: the prospector names it at the end of its
  report; add it to the disease table with its page.

## Keeping it

Every row carries the date it was checked. A row older than a year is
re-read before the prospector relies on its description of the page, and
the prospector opens the page itself on every request regardless. There is
no scheduled refresh yet; that is the poller the issue describes, which
would read the Feed column and is not built.
