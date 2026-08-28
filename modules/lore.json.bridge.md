# Brygga Crucible ↔ rise_pipeline (28 aug 2026)

Samma sak, två verktyg. Crucible v7 (`crucible.py --module vinnova-ekosystem-vv`) läser en PDF
och poängsätter mot utlysningens kriterier, mallens frågor och 27 utlysningstermer, deterministiskt.
`grant-pipeline/rise_pipeline` genererar texten och poängsätter fem axlar (utlysning, RISE,
behovsägare, WINNIIO:s affär, SMILE) med parametrisk design tills alla når golvet och summan slutar stiga.

Kopplingar som nu finns:
- `rise_pipeline/axlar.py` → `UTL_TERMER` = Crucibles `CALL_TERMS` (utlysningsaxeln räknar täckning).
- `rise_pipeline/noder.py::crucible()` kör Crucible på varje GEN-pdf som andra åsikt; utfall i `out/crucible_<label>.json`.

Fynd 28 aug: Crucible läser inte Word-tabellerna i PDF:er byggda ur Vinnovas mall (TABELL 1–3 rapporteras
SAKNAS trots att de finns; TABELL 4 hittas). Excellence 1,0–1,2 av 10 på både inlämnad text och GEN_3 beror
delvis på det. Åtgärd: tabellextraktion med pdfplumber/ layout-läge, eller läs docx direkt när den finns.

Vad Crucible kan ta från rise_pipeline: axlar per intressent (partner, behovsägare, eget hus) som
moduler med parameterfil + `prov`, och loopen (generera tills radarn är full), i stället för enbart analys.

## Åtgärdat 28 aug 14:20

`_extract_from_pdf` läser nu tabeller med `page.find_tables()` och lägger dem som
"cell | cell"-rader efter sidtexten, som .docx-vägen redan gjorde. Bevis: GEN_6.pdf gick från
TABELL 1–3 SAKNAS till 4/4 OK, identiskt med GEN_6.docx (composite 8,4 i båda). Inlämnad VIKI:
composite 9,7 (potential 9,5 · aktörer 10,0 · genomförbarhet 9,8), mallfrågor kvar: M3.1.

`module_scores` ligger redan i JSON:en — `rise_pipeline/noder.crucible()` läser den nu, och
`axlar.axel_kvalitet` gör composite×10 till pipelinens sjätte axel med `mall_missing`,
formella varningar och saknade tabeller som återkoppling till nästa utkast.
Prov: `prov_noder.py --sidor` K1 — jämställdhetsinnehållet borttaget ur brödtexten sänker
9,7 → 8,5, alltså 97 → 85 på axeln.
