# ThermoHuddle — Developmental Reframe: Paste-Ready Drafts

_Drop-in replacement text for the sections that change when the design shifts from
**experimental** to **developmental**. Everything else (framework, Ch. 2 RRL, system
descriptions) stays. Written to match the register of DESIGN-1-TANVERSE._

---

## 1. §1.3 Research Paradigm — one-line addition

Append after the IPO table (before the paragraph explanation):

> This study employs a **developmental research design**, following the
> Input–Process–Output model to depict the transformation of environmental and
> behavioral inputs into hardware actuation, system evaluation, and cloud
> telemetry.

_(The IPO model itself does not change — it is the natural paradigm of a
developmental study. Only the label is added.)_

---

## 2. §1.4 Statement of the Problem (FULL REPLACEMENT)

> This study aims to design, develop, and evaluate ThermoHuddle, an Edge AI-driven
> smart chick brooder that infers behavioral thermal comfort through spatial
> dispersion analysis and cascade control.
>
> Specifically, this study seeks to answer the following questions:
>
> **1. How may ThermoHuddle be developed in terms of:**
>    a. hardware integration of the environmental, acoustic, and vision sensing
>       subsystems with the cascade heating control on a Raspberry Pi 5; and
>    b. software integration of spatial dispersion analysis (NND, Ripley's K,
>       Shannon occupancy entropy), acoustic distress detection (MFCCs), and
>       closed-loop telemetry?
>
> **2. What is the performance of the developed system in terms of:**
>    a. classification accuracy of the five comfort states (*Too Cold,
>       Comfortable, Too Hot, Draft, Crowding Risk*);
>    b. thermal stability and setpoint tracking of the cascade controller
>       compared with a conventional single-point thermostat;
>    c. local edge processing latency; and
>    d. telemetry responsiveness of the web dashboard?
>
> **3. What is the level of acceptability of the developed system in terms of
> functionality, reliability, usability, and maintainability (ISO/IEC 25010) as
> evaluated by intended users and experts?**
>
> **4. What recommendations may be proposed based on the results of the
> evaluation?**

_Note on Q2b: the thermostat comparison survives, but as a **descriptive
benchmark** (report both numbers, no significance test) — this is the standard
developmental way to keep a comparison without becoming an experiment._

---

## 3. §1.5 Hypothesis — REPLACE (or delete)

> **Hypothesis**
>
> The developed ThermoHuddle system is acceptable in terms of functionality,
> reliability, usability, and maintainability as rated by the respondents.

_(Alternative accepted by most panels: delete the Hypothesis section entirely.
Developmental papers typically test nothing; the single acceptability hypothesis
is the safest middle ground if the template requires one.)_

---

## 4. §3.1 Research Design (NEW SECTION — full text)

> **3.1 Research Design**
>
> This study employs a developmental research design, which focuses on the
> systematic creation and evaluation of a working prototype rather than on the
> statistical testing of relationships between variables. The development of
> ThermoHuddle followed five phases:
>
> **Phase 1 — Analysis.** Review of related literature on smart brooders,
> behavioral thermal comfort, computer vision, and multimodal sensing; definition
> of system requirements (five comfort states, safety overrides, 14-day brooding
> period, 1.0 m × 1.0 m brooder, up to 50 chicks).
>
> **Phase 2 — Design.** Design of the hardware (sensor array, zero-cross AC
> dimmer, relay bank, Raspberry Pi 5), the five-service software architecture
> (th-sensord, th-visiond, th-audiod, th-brain, th-uplink), the cascade control
> scheme, and the network and telemetry design (MQTT, SQLite outbox, Supabase,
> web dashboard).
>
> **Phase 3 — Development.** Construction of the prototype and implementation of
> the software, using unit testing of each component as it is integrated.
>
> **Phase 4 — Testing.** Component/unit testing, integration testing, and system
> testing of the assembled prototype, including classification checks against
> known brooder conditions and controller response measurement.
>
> **Phase 5 — Evaluation.** Descriptive evaluation of system performance
> (classification accuracy, thermal stability, latency, telemetry responsiveness)
> and acceptability evaluation by respondents using an ISO/IEC 25010-based
> instrument.
>
> The evaluation data gathered in Phases 4 and 5 are analyzed **descriptively**
> using frequency, percentage, and weighted mean. No inferential hypothesis
> testing is performed; a full controlled experiment comparing arms is recommended
> as future work (Chapter 5).

---

## 5. §3.x Evaluation Instrument (NEW SECTION — full text)

> **3.x Evaluation Instrument**
>
> System acceptability was measured using a researcher-made evaluation
> instrument based on the ISO/IEC 25010 software quality model, covering the
> characteristics **functional suitability/functionality, reliability, usability,
> and maintainability**. Each characteristic contains 4–6 indicators rated on a
> four-point Likert scale:
>
> | Scale | Range | Interpretation |
> |---|---|---|
> | 4 | 3.50 – 4.00 | Highly Acceptable |
> | 3 | 2.50 – 3.49 | Acceptable |
> | 2 | 1.50 – 2.49 | Slightly Acceptable |
> | 1 | 1.00 – 1.49 | Not Acceptable |
>
> The instrument was validated by [adviser / expert validator names]. Respondents
> were [N = ___] composed of [e.g., ___ poultry raisers/small-scale farmers,
> ___ IT/computer engineering experts]. Results are presented per indicator,
> per characteristic, and overall as weighted means with their interpretations.
>
> _(Fill the brackets with your actual validators and respondents. If the
> department requires a 5-point scale, relabel the ranges — the structure is
> unchanged. For Chapter 4, report the survey results in a table with the same
> layout as Table 4.2.)_

---

## 6. Chapter 4 — Evaluation section (replacement for the comparison framing)

> **4.x System Evaluation**
>
> The evaluation of the developed system covers (a) functional testing results
> (Tables 4.1–4.2), and (b) a 14-day brooding evaluation during which the system
> operated on live chicks. Reported descriptively:
>
> | Metric | Instrument / Source |
> |---|---|
> | Comfort-state classification accuracy | Agreement of system state vs. labeled reference observations; confusion matrix |
> | Time inside comfort band | % of 30-s behavior windows with state = COMFORTABLE (per day) |
> | Thermal stability | Floor-temperature deviation from the age-based setpoint (34 → 29 °C); max deviation, time-to-recover |
> | Response / stabilization time | control_events table (time from state change to trim completion; time to return to band) |
> | Crowding episodes | count + duration; alarm acknowledgement logs |
> | Survival | % survival at day 14, deaths with cause attribution |
> | Energy | lamp duty cycle × heater wattage, per day |
> | Latency / uptime | pipeline frame-processing latency; service uptime %; dashboard poll success % |
> | Acceptability | ISO 25010 survey, weighted means (§3.x instrument) |
>
> Results are presented as means, percentages, and ranges per day and overall.
> These values are compared with figures reported in related literature to
> contextualize performance, and with the traditional thermostat operation
> monitored alongside as a reference point.

_(All Chapter 4 data tables from the old plan — runs/deaths/arm views in
Supabase — remain exactly as built; only the framing changes from "test the
hypothesis" to "describe the evaluation.")_

---

## 7. Chapter 5 — shape

- **Summary** — what was developed, per phase of the research design.
- **Conclusion** — answers each SOP question in order (Q1 integration outcome,
  Q2 performance figures, Q3 acceptability rating + interpretation).
- **Recommendations** — adopt/deploy suggestions for small-scale farmers,
  hardware hardening, **and the future-work paragraph: a controlled Arm A vs
  Arm B experiment with adequate statistical power to quantify survival
  effects** (pull the n=50 power rationale from Build Guide §7 here — it becomes
  the justification for why the experiment belongs in future work, not a
  weakness of this study).

---

## 8. Housekeeping sweep (fix before next adviser review)

| Location | Issue | Fix |
|---|---|---|
| Title page / Abstract | "aispersion" (subtitle typo), "INTROaUCTION" | "dispersion", "INTRODUCTION" |
| Ch. 3 | "(chan)" author comments ×3; "aesign", "aiagram" | remove comments, fix typos |
| Ch. 3 numbering | Figures jump 3.1 → 3.3 → 3.4…; sections 3.3–3.7 but no 3.2 | renumber sequentially |
| §1.2 vs §1.3 | duplicate IPO content | keep the formatted table; delete the scrambled text-block version |
| Ch. 4 | **Soil-thesis leftovers**: Tables 4.3–4.6 (air pollutants, soil data Apr/May 2026), heavy-metal thresholds, HeavyMetals.xlsx / LUCAS_HM_merged.csv, duplicate "Training Results" | DELETE — belongs to a different capstone |
| Front matter | DATE, ADVISER, INSTRUCTOR, RESEARCHERS blank | fill in |
| Footers | "COGNATE 2" running head on every page | confirm correct subject label with adviser |
