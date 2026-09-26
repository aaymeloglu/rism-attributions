# RISM: naming the anonymous

[RISM](https://rism.online/) (Répertoire International des Sources Musicales) catalogues about
1.6 million music manuscripts and prints. About 297,000 are listed under "Anonymus", and most
of those carry incipits, the encoded opening bars of each movement. This repository searches
those incipits against the attributed ones and checks every match by hand, one genre at a time.

The results, with each anonymous copy's movements rendered next to the attributed copy's, are at
**https://aaymeloglu.github.io/rism-attributions/**.

## Results so far (symphonies, 26 September 2026)

878 anonymous symphonies with incipits were searched. 133 leads were reviewed covering 125
anonymous sources:

| Verdict | Sources |
|---|---|
| confirmed | 58 |
| conflicting attribution | 1 |
| probable | 7 |
| unresolved | 4 |
| already identified in the record | 11 |
| rejected | 44 |

Many anonymous "symphonies" turn out to be opera overtures (Galuppi, Sacchini, Mysliveček,
Cimarosa, Paisiello, Sarti, Naumann's *La clemenza di Tito*), or arrangements of quartets and
sonatas. One symphony (PL-SA 141/A III 41) matches copies attributed both to Hasse and to
Röllig. A further 12 pairs of anonymous copies match each other on two or more movements; they
are listed on the site as [anonymous concordances](https://aaymeloglu.github.io/rism-attributions/concordances.html).

A match means RISM holds an attributed copy of the same music. It does not settle a disputed
authorship, and the composers' printed thematic catalogues may already list some of these
copies. Nothing has been reported to RISM yet. See [METHOD.md](METHOD.md) for the pipeline,
what each verdict means and the limits. The research was done by Claude (an LLM).

## Layout

```
data/verdicts.csv                 hand verdict and note for every lead (the source of truth)
data/attributions.json            generated: verdicts joined with RISM records and incipits (what the site shows)
data/anonymous_concordances.json  generated: anonymous copies matching each other on 2+ movements
data/genres.json                  burndown: anonymous sources with incipits per RISM subject
runs/<genre>/results.json         search hits per anonymous source
runs/<genre>/leads.json           graded leads with evidence
tools/                            rism.py (cached API client), pae.py (Plaine & Easie pitches), discover/leads/export/genres
docs/                             the site; python3 docs/_build_site.py regenerates it (stdlib only)
tests/                            data/site consistency; CI fails if docs/ is stale
```

## Data

Catalogue data and incipits are from RISM, licensed CC BY 4.0. Incipits on the site are rendered
in the browser with [Verovio](https://www.verovio.org/).
