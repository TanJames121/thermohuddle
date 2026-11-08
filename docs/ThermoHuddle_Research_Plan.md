# ThermoHuddle — Research Plan (paper-mirror)

_This document mirrors the current manuscript text of DESIGN-1-TANVERSE for the
sections that changed on 2026-11-05. The **paper is the source of truth**; the
Build Guide and Overview are synced to this file. Keep all three in step —
Build Guide §8 explains the three-artifact sync rule._

**Provenance:** text below is taken from the team's revision ("Untitled
document", received 2026-11-05), lightly reformatted to Markdown. No claim was
invented or strengthened; cautious clauses are preserved verbatim in meaning.

---

## 1.2 Conceptual Framework

The study is anchored in the relationship among brooder conditions, observable
chick behavior, and automatic environmental adjustment. Brooder floor
temperature, ambient temperature, humidity, airflow, and ammonia-related
air-quality indications constitute environmental inputs. Chick position, local
density, spatial dispersion, and vocalizations constitute behavioral
observations. These inputs are analyzed to estimate operational states that may
require a heater adjustment, a safety response, or continued monitoring.

Three spatial descriptors support the proposed behavioral inference:

- **NND** quantifies how close detected chick locations are to their nearest neighbors.
- **Ripley's K** assesses clustering across selected distance scales.
- **Shannon occupancy entropy** describes the distribution of detected chicks across a 4 × 4 floor grid.

The descriptors are considered together with chick occupancy near the heater
and enclosure edges, temperature readings, and audio-derived features. Since
similar distributions may arise from more than one cause, the decision logic is
intended to use contextual checks and confidence limits rather than assuming
that one statistic alone identifies thermal discomfort.

The control framework has two coordinated levels. The outer behavioral
supervisor determines whether a small change in the age-appropriate
floor-temperature setpoint is justified by persistent observations. The inner
PID controller uses measured floor temperature to regulate heater output within
predefined limits. Hazard functions, such as over-temperature cutoff, suspect
crowding, and abnormal air-quality indications, operate as protective overrides
rather than as routine setpoint recommendations. This arrangement forms a
closed feedback process: the system observes flock response and floor
temperature after actuation and updates subsequent decisions. Local control is
designed to remain functional without internet connectivity; remote monitoring
provides a secondary information channel.

---

## 1.4 Statement of the Problem

This study aims to determine how ThermoHuddle can be designed, implemented, and
evaluated as a closed-loop smart brooder that uses spatial dispersion and
supplementary sensor information to infer chick conditions and support
automatic thermal control. Specifically, it seeks to answer the following
questions:

1. How can the Raspberry Pi 5, overhead NoIR camera, INMP441 microphone,
   DS18B20 floor-temperature array, DHT22 sensor, MQ-137 gas-sensing module,
   heating controller, ventilation fans, and independent hardware safety cutoff
   be integrated into a functional brooder prototype?

2. How accurately can the proposed spatial-analysis and multimodal decision
   process classify the five operational conditions — Too Cold, Comfortable,
   Too Hot, Draft, and Crowding Risk — against independently annotated
   reference observations?

3. How effectively can the behavior-guided supervisory layer and inner PID loop
   regulate floor temperature, and how reliably can the system detect, signal,
   and respond to monitored hazards without exceeding established safety
   limits?

4. What is the performance of ThermoHuddle in terms of (a) classification
   accuracy and class-wise performance; (b) percentage of valid monitoring time
   within the approved floor-temperature band; (c) temperature response,
   stabilization time, and overshoot; (d) hazard-alert latency and delivery;
   (e) observed 14-day chick survival and completeness of incident records;
   (f) image-processing latency; (g) local-control continuity and
   remote-dashboard availability; and (h) end-user and technical-expert
   evaluation?

---

## 1.7 Scope and Delimitations of the Study

The study covers the development and evaluation of one small-scale, enclosed
poultry brooder with a nominal floor area of 1.0 m × 1.0 m and a proposed
capacity of up to 50 day-old chicks observed during their first 14 days. The
stated capacity and environmental limits are design assumptions that require
approval under the applicable husbandry and animal-welfare protocol before any
live trial.

The system uses a Raspberry Pi 5, NoIR Camera Module 3 with suitable infrared
illumination, INMP441 microphone, four DS18B20 floor-temperature probes, DHT22
ambient sensor, MQ-137 with ADS1115 analog-to-digital conversion, ventilation
fans, and a nominal 100 W or 150 W ceramic infrared heat source. Selection of
the final emitter rating and compatible control interface is subject to
electrical and thermal verification. The proposed analysis includes NND,
Ripley's K, and Shannon occupancy entropy; acoustic features provide supporting
evidence for possible distress. The system will log readings and events locally
and will synchronize monitoring information to a Supabase-backed dashboard when
network access is available.

The research is limited to flock-level observation within one prototype
enclosure. The camera analysis estimates positions and distribution and is not
intended to establish reliable identities or continuous histories for each
individual chick. The five system outputs are operational monitoring
conditions, not veterinary diagnoses or mutually exclusive biological
explanations; priority rules will be applied where signs overlap. The study
does not cover large commercial houses, additional bird species, gas-fired
heating, refrigeration, disease detection, or evidence of commercial-scale cost
effectiveness. The MQ-137 output is treated as a relative ammonia-related
indication unless calibration and independent reference comparison support
defensible concentration readings. An internet connection is required for
remote dashboard access and synchronization, but not for core local sensing and
control. The prototype does not include an uninterruptible power supply. Chick
survival is reported descriptively; without a controlled comparative husbandry
study, the results cannot establish that ThermoHuddle causes a change in
mortality.

---

## 3.1 Research Methodology

This chapter describes the proposed development and evaluation of ThermoHuddle.
The study will apply a developmental research approach to design and refine the
prototype and a descriptive quantitative approach to summarize operational
performance and user evaluations. The methodology is organized so that each
research question corresponds to observable tests, recorded data, and an
analysis procedure that can be presented in Chapter 4.

The work will use the six-stage prototype development cycle: requirements
gathering and analysis, quick design, prototype building, verification and
subsystem testing, iterative refinement, and final implementation and
evaluation. Unless actual implementation and testing records are available, all
procedures in this chapter are presented as planned activities, not completed
experiments.

---

## 3.2 Research Method and Prototype Development

**Stage 1 — Requirements Gathering and Analysis.** The researchers will
identify the functional and safety needs of the 1.0 m × 1.0 m brooder, the
proposed 14-day observation schedule, the planned chick capacity, temperature
and humidity measurement locations, sensor and actuator interfaces, camera
field of view, and record-keeping requirements. The source draft proposes an
age-dependent 34 °C to 29 °C thermal schedule, 50–70 % relative humidity, and
an ammonia alert criterion below 25 ppm. These figures will be treated as
preliminary design values and verified with qualified poultry-care guidance
before any live deployment. The reference quantity (floor temperature at the
defined sensing locations) will be fixed and used consistently in testing and
reporting.

**Stage 2 — Quick Design.** The researchers will prepare an architecture
connecting the NoIR camera, microphone, sensors, and actuator controls to the
Raspberry Pi 5, with the five proposed software services: th-sensord
(environment and actuator interface), th-visiond (frame acquisition and spatial
analysis), th-audiod (audio capture and features), th-brain (state inference
and supervisory control), and th-uplink (local records and remote
synchronization). Local MQTT messaging or an equivalent documented local
transport will connect services. The database interface will be tested
separately from the safety-critical control loop.

**Stage 3 — Prototype Building.** The researchers will assemble the enclosure
and develop sensor interfaces, camera mounts, protected electrical
compartments, heater actuation, ventilation, and the local software modules.
Standalone ESP32 test benches may be used for hardware verification as proposed
in the source draft, but the final control topology and ownership of sensor
inputs will be documented to avoid conflicting output commands. The final
installation will include a KSD301 or equivalent hardware-rated
over-temperature cutoff independent of software, protective grounding,
appropriate overcurrent protection, isolation, and wiring inspection by
qualified personnel.

**Stage 4 — Verification and Subsystem Testing.** Before live-bird operation,
each component will be checked against defined acceptance criteria. Sensor
channels will be compared with suitable references; camera frames will be
checked for coverage and chick detection; audio feature extraction will be
verified on labeled samples; local messaging, logging, dashboard
synchronization, and fan operation will be tested; and heater modulation and
fail-safe behavior will be evaluated with appropriate thermal loads. Software
services will be tested individually and together, including restarts and
intentional network interruption.

**Stage 5 — Iterative Refinement.** The researchers will tune detection,
classification, and control using only designated pilot or development data.
The source proposes a 10-minute persistence or dwell requirement, a maximum
supervisor adjustment rate of 1 °C per hour, a minimum confidence gate of
0.60, and temporary suppression of behavior-based setpoint changes during
disruptive fan events. These are initial design settings and will be validated;
they must not be presented as evidence-based optimal values without results.
Following tuning, model and thresholds will be frozen before the final
evaluation dataset is assessed.

**Stage 6 — Final Implementation and Evaluation.** The researchers will execute
documented bench tests and a proposed 14-day brooding observation after
required animal-welfare and safety approvals. Sensor readings, predicted
states, human reference labels, heater commands, alarms, failure events, and
welfare observations will be time-stamped. Intended users and technical experts
will evaluate the demonstrable system using a structured instrument adapted to
relevant ISO/IEC 25010 quality characteristics.

---

## 3.4 Description of the Respondents

Two groups will be asked to evaluate the demonstrated prototype. Intended
end-users will include small-scale poultry raisers, backyard chick caretakers,
and livestock technicians with practical brooding experience. They will assess
the clarity of readings and warnings, ease of operation, accessibility of the
dashboard, and perceived usefulness of the system. Technical experts will
include qualified computer/electronics engineers, embedded-systems
practitioners, software developers, or instructors with relevant technical
competence. They will assess observable functionality, performance,
reliability, maintainability, electrical/software integration, and the adequacy
of protective behaviors.

Survey respondents are distinct from the trained observers who will produce
reference classifications for image or video evaluation. Reference annotators
must follow an operational labeling guide and, where possible, annotate samples
independently before disagreements are resolved.

---

## 3.5 Population of the Study and Sampling Technique

The target acceptability sample is 30 respondents: 15 intended end-users and 15
technical experts. Purposive sampling will be used because respondents need
practical or technical familiarity with the system being assessed. Inclusion
criteria and selection records will be documented, and completed participation
counts will be reported rather than presuming that all target respondents
participate. Consent will be obtained before administering the survey.

The quantitative system-performance dataset will not consist of these 30
surveys. It will comprise time-stamped sensor and controller logs, annotated
image or audio samples, and incident records acquired during bench verification
and the planned brooding observation. The exact number of valid frames, audio
segments, control tests, and observation hours will be reported after
collection. Development/tuning observations and final evaluation observations
will be kept separate to limit overly optimistic estimates.

---

## Sync map (what changed vs. the previous docs)

| Topic | Previous repo-doc state | Paper-mirror state (now authoritative) |
|---|---|---|
| SOP | 4 questions (develop / performance / acceptability / recommendations) | 4 questions rewritten: integration, classification accuracy, control + hazard response, 8-part performance list |
| Design framing | developmental; hypotheses removed | developmental + **descriptive quantitative**; six-stage cycle replaces the five-phase list |
| Safety hardware | software interlocks + heater-fail rules | adds **KSD301 hardware over-temp cutoff, grounding, overcurrent, isolation, wiring inspection** |
| Gas sensing | MQ-137 ppm direct | MQ-137 + **ADS1115**; ppm only "relative indication" unless calibrated |
| Parameters | 34→29 °C schedule, 25 ppm, dwell 10 min, 1 °C/h, conf 0.60 presented as design constants | same values but **"preliminary design values" pending qualified poultry-care guidance** |
| Live trial | proposed 14-day run | 14-day run **only after animal-welfare/safety approval**; capacity limits are assumptions requiring approval |
| Respondents | generic "experts and end-users" | **30 respondents = 15 end-users + 15 technical experts**, purposive sampling, consent documented |
| Labels | human labeling mentioned | **survey respondents ≠ reference annotators**; labeling guide + independent annotation + disagreement resolution |
| Data reporting | fixed table structure | counts of valid frames/segments/tests/hours reported **after collection**; tuning data kept separate from evaluation data |
