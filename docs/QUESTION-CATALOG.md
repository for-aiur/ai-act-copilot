# Question catalogue

164 authored questions covering 114 stored passages. These are engineering review prompts, not legal determinations or proof of evaluated domain coverage.

The model receives a bounded subset. Editorial ordering chooses up to four detailed options and two context options per retrieved passage; not every bank question is offered on every scan. See [selection and limits](QUESTIONS.md).

## annex-iii-1-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **biometrics_identification** (developer, context): Is this used to identify someone against a gallery, or solely to verify a claimed identity, and where is it deployed?
- **biometrics_purpose** (developer, context): Whose faces are processed, for what purpose, and in what deployment setting?
- **annex_iii_1_a_evidence** (developer, evidence): Which matching flow proves this identifies a person against a gallery rather than only verifying their claimed identity, and who acts on a match?
  - Evidence to inspect: Identity-flow diagram, gallery configuration and downstream decision trace.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-1-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_1_b_evidence** (developer, evidence): Which sensitive attributes are inferred or assigned by this categorisation model, and where can you trace how a category changes treatment of a person?
  - Evidence to inspect: Attribute schema, inference outputs and downstream routing tests.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-1-c

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_1_c_evidence** (developer, evidence): Which output is treated as an inferred emotion, and what real decision changes because of that output?
  - Evidence to inspect: Output taxonomy, intended-use record and decision-flow examples.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_2_evidence** (developer, evidence): Which infrastructure safety function depends on this prediction, and what happens to people or essential supply if it fails?
  - Evidence to inspect: Safety dependency map and fault-injection or failover test report.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-3-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_3_a_evidence** (developer, evidence): Can you trace how an admission score changes a learner's access or assignment, including borderline and overridden decisions?
  - Evidence to inspect: Admission decision traces, threshold policy and override records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-3-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_3_b_evidence** (developer, evidence): Which evaluation output changes a learner's grade or learning path, and what evidence shows how disputed results are reviewed?
  - Evidence to inspect: Learning-outcome mapping, grading examples and review procedure.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-3-c

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_3_c_evidence** (developer, evidence): Which model output determines the education level a learner can receive, and who can correct a mistaken placement?
  - Evidence to inspect: Placement rules, representative cases and correction workflow.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-3-d

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_3_d_evidence** (developer, evidence): What behaviour triggers an exam-monitoring flag, and how is a false positive checked before a student faces consequences?
  - Evidence to inspect: Flag definitions, false-positive evaluation and adjudication records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-4-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **recruitment_human_review** (developer, context): Will these scores affect real hiring decisions in the EU, and who reviews the shortlist?
- **recruitment_real_use** (developer, context): Are these predictions used only in testing, or to select actual applicants?
- **annex_iii_4_a_evidence** (developer, evidence): Can you replay one applicant's path from input to score, cutoff and recruiter decision, showing exactly where the score influences selection?
  - Evidence to inspect: Versioned decision trace, shortlist cutoff policy and recruiter action log.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-4-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_4_b_evidence** (developer, evidence): Which employee decisions depend on these scores, and can a reviewer trace the personal behaviour or characteristics used in task allocation or performance assessment?
  - Evidence to inspect: Feature inventory, employee decision map and review records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-5-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_5_a_evidence** (developer, evidence): Which benefit or service can this score grant, reduce, revoke or reclaim, and how can an erroneous eligibility result be corrected?
  - Evidence to inspect: Eligibility workflow, decision examples and correction records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-5-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_5_b_evidence** (developer, evidence): Does this output evaluate a person's creditworthiness or only detect financial fraud, and which downstream decision confirms that distinction?
  - Evidence to inspect: Intended-use assessment, score consumers and lending decision traces.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-5-c

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_5_c_evidence** (developer, evidence): Which life or health insurance risk or premium changes because of this output, and where is that use documented?
  - Evidence to inspect: Insurance product scope, pricing inputs and decision records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-5-d

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_5_d_evidence** (developer, evidence): How does this ranking change emergency dispatch or triage priority, and what happens when a time-critical case receives a low score?
  - Evidence to inspect: Dispatch flow, escalation rules and delayed-response test cases.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-6-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_6_a_evidence** (developer, evidence): Which law-enforcement decision uses this victim-risk assessment, and where are the affected person's context and human review recorded?
  - Evidence to inspect: Deployment-purpose record, risk-output consumers and review trail.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-6-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_6_b_evidence** (developer, evidence): What does this law-enforcement polygraph-like output claim to measure, and how does an operator use or challenge it?
  - Evidence to inspect: Measurement definition, operating procedure and reviewed case records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-6-c

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_6_c_evidence** (developer, evidence): How does this model alter an assessment of evidence reliability during an investigation, and where can an investigator inspect the underlying reasoning?
  - Evidence to inspect: Evidence-analysis workflow, output provenance and review records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-6-d

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_6_d_evidence** (developer, evidence): Which personal characteristics or past behaviour feed this offending-risk assessment, and what documented use distinguishes it from a prohibited use requiring separate review?
  - Evidence to inspect: Feature list, intended-use assessment and specialist review record.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-6-e

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_6_e_evidence** (developer, evidence): Where does this profiling output enter detection, investigation or prosecution, and which human decision can you trace to it?
  - Evidence to inspect: Profiling purpose, processing flow and investigator decision trail.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-7-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_7_a_evidence** (developer, evidence): Which migration or border procedure uses this polygraph-like output, and where is its influence on the person's case recorded?
  - Evidence to inspect: Procedure scope, output interpretation guide and case decision trace.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-7-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_7_b_evidence** (developer, evidence): Which security, migration or health risk is inferred about a person entering a Member State, and who reviews an adverse assessment?
  - Evidence to inspect: Risk definition, deployment scope and adverse-case review records.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-7-c

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_7_c_evidence** (developer, evidence): How does this output influence an asylum, visa or residence assessment, including the reliability assigned to an applicant's evidence?
  - Evidence to inspect: Case assessment flow, evidence provenance and reviewer actions.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-7-d

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_7_d_evidence** (developer, evidence): Does this migration or border use identify a person against other records or only verify a travel document, and how is the distinction enforced?
  - Evidence to inspect: Matching configuration, document-verification flow and integration tests.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-8-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_8_a_evidence** (developer, evidence): Which judicial or dispute-resolution assessment uses this output, and what lets the responsible person independently inspect the facts and legal reasoning?
  - Evidence to inspect: Intended-use record, output provenance and judicial review workflow.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iii-8-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)

- **annex_iii_8_b_evidence** (developer, evidence): Will voters encounter this output or does it only support internal campaign logistics, and what decision about voting behaviour is it intended to influence?
  - Evidence to inspect: Audience map, distribution channels and campaign-purpose assessment.
  - When relevant: Only when intended use and affected decisions plausibly match this specific Annex III use case; classification remains to be assessed.

## annex-iv-1-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_a_evidence** (developer, evidence): Can a reviewer identify the exact provider, intended purpose and released system version from the documentation accompanying this deployment?
  - Evidence to inspect: Versioned system description and release-to-document mapping.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-1-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_b_evidence** (developer, evidence): Which external systems supply inputs or consume outputs, and where are their interfaces and failure assumptions documented?
  - Evidence to inspect: Integration diagram, interface contracts and dependency failure tests.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-1-c

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_c_evidence** (developer, evidence): Which software and firmware versions were validated together, and what evidence triggers revalidation after an update?
  - Evidence to inspect: Dependency lockfiles, compatibility matrix and update test records.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-1-d

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_d_evidence** (developer, evidence): Which packaged, embedded or API-delivered variants exist, and how is each mapped to its documented behaviour and release version?
  - Evidence to inspect: Distribution inventory, API versions and release manifest.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-1-e

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_e_evidence** (developer, evidence): What hardware assumptions were used to validate latency and numerical behaviour, and are they met in this deployment?
  - Evidence to inspect: Hardware requirements, target-device inventory and benchmark records.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-1-f

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_f_evidence** (developer, evidence): For an AI component embedded in a product, where do the product images and markings identify the component and its internal placement?
  - Evidence to inspect: Labelled product images, component drawings and marking records.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-1-g

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_g_evidence** (developer, evidence): Which deployed user-interface version is described, and can its actual output and warning states be matched to that description?
  - Evidence to inspect: UI screenshots, interaction specification and version mapping.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-1-h

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_1_h_evidence** (developer, evidence): Can an operator follow the supplied instructions to interpret an output and respond to an error using the actual deployed interface?
  - Evidence to inspect: Operator instructions and a recorded walkthrough of error handling.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-a

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_2_a_evidence** (developer, evidence): Which pretrained components were reused or modified, and can you reconstruct their contribution to this model from a versioned development record?
  - Evidence to inspect: Component versions, modification history and development provenance.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **training_third_party_lineage** (developer, evidence): For each pretrained dependency, which exact artifact was used, what was changed, and what evaluation was repeated after integration?
  - Evidence to inspect: Artifact hashes, integration diff and post-integration evaluation.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-b

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **training_parameters** (developer, context): Where are the training objective, hyperparameter choices and their trade-offs documented and evaluated?
- **annex_iv_2_b_evidence** (developer, evidence): Why were this objective and these hyperparameters chosen, and which comparison shows the resulting accuracy, subgroup and failure trade-offs?
  - Evidence to inspect: Experiment ledger, configuration hashes and comparative evaluation report.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **parameters_selection_tradeoff** (developer, evidence): Which alternative objective or parameter setting was rejected, and what measured trade-off justified choosing the released configuration?
  - Evidence to inspect: Comparative experiment results, chosen configuration and decision rationale.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-c

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_2_c_evidence** (developer, evidence): Can you reconstruct the training and inference architecture, including the compute resources and component dependencies used in validation?
  - Evidence to inspect: Architecture diagram, training job manifest and compute configuration.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-d

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **training_datasheet** (developer, context): Where is the datasheet recording training methodology, dataset provenance, selection, labelling and cleaning?
- **annex_iv_2_d_evidence** (developer, evidence): Can you reproduce a training dataset from its source, selection, labelling and cleaning records, including the rows each operation removed?
  - Evidence to inspect: Dataset manifest, transformation history, label guide and datasheet.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-e

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_2_e_evidence** (developer, evidence): Which output interpretation and intervention needs were assessed, and how do the documented controls enable the human reviewer to meet them?
  - Evidence to inspect: Oversight assessment, interpretation tools and intervention test records.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-f

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_2_f_evidence** (developer, evidence): Which future model changes were predetermined, and what documented checks bound their effect on performance and the assessed requirements?
  - Evidence to inspect: Approved change envelope, acceptance tests and change-control record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-g

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_2_g_evidence** (developer, evidence): Can you reproduce the reported evaluation using the recorded dataset, model version and metrics, including subgroup results and responsible sign-off?
  - Evidence to inspect: Versioned test data, executable evaluation, dated report and sign-off.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **training_split_leakage** (developer, evidence): How did you test for duplicate people, time leakage or shared source records across training and evaluation splits before trusting the reported results?
  - Evidence to inspect: Split manifests, entity-overlap checks and time-based holdout tests.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **training_tuning_holdout** (developer, evidence): Which evaluation data remained untouched during feature selection and hyperparameter tuning, and can you reproduce the final holdout result?
  - Evidence to inspect: Tuning history, dataset access/version records and final holdout run.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-2-h

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_2_h_evidence** (developer, evidence): Which cybersecurity controls protect this model and its interfaces, and where are their implementation and verification recorded?
  - Evidence to inspect: Threat model, control inventory and security test report.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_3_evidence** (developer, evidence): Which known limitations and subgroup performance differences must an operator see before using this output, and how are they monitored in deployment?
  - Evidence to inspect: Performance breakdown, input specification and monitoring plan.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_4_evidence** (developer, evidence): Why do these performance metrics represent the real consequences of mistakes rather than only aggregate prediction quality?
  - Evidence to inspect: Metric rationale, error-cost analysis and stakeholder acceptance record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-5

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_5_evidence** (developer, evidence): Can each documented hazard be traced to an assessment, mitigation, test and owner in the system's risk-management record?
  - Evidence to inspect: Risk register with linked mitigation and verification evidence.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-6

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_6_evidence** (developer, evidence): Which model or data changes occurred after release, and where is the impact of each change on behaviour and evaluation recorded?
  - Evidence to inspect: Versioned change history and impact assessments.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-7

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_7_evidence** (developer, evidence): Which cited harmonised standards or alternative technical solutions support the documented controls, and is their version and status recorded?
  - Evidence to inspect: Standards register, version references and control-to-standard mapping.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-8

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_8_evidence** (developer, evidence): Where is the declaration of conformity for this exact system version, and who owns checking that the deployed version matches it?
  - Evidence to inspect: Signed declaration, system identifier and release mapping.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## annex-iv-9

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)

- **annex_iv_9_evidence** (developer, evidence): Which post-market signals, review schedule and escalation owners are specified for detecting performance or risk changes after deployment?
  - Evidence to inspect: Post-market monitoring plan, signal definitions and escalation procedure.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-4a-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-4a)

- **bias_audit_deletion** (developer, context): For special-category data used specifically for bias auditing, how is access restricted and deletion triggered after correction or retention expiry?
- **article_4a_1_evidence** (developer, evidence): For this special-category bias audit, what evidence shows anonymised or synthetic data was insufficient, and who can verify access limits and timely deletion?
  - Evidence to inspect: Necessity assessment, access records, retention rule and deletion test evidence.
  - When relevant: Only for exceptional special-category personal-data processing specifically for bias detection/correction; not general PII erasure.
- **bias_audit_deletion_copies** (developer, evidence): For special-category data used in this exceptional bias audit, which test verifies deletion of working copies and exports when correction or retention expiry triggers removal?
  - Evidence to inspect: Scoped copy inventory, deletion trigger and end-to-end deletion test.
  - When relevant: Only for exceptional special-category personal-data processing specifically for bias detection/correction; not general PII erasure.
- **bias_audit_access_proof** (developer, evidence): For this exceptional special-category bias audit, can you show which identities accessed the records and how unauthorised access or onward transfer is prevented?
  - Evidence to inspect: Access-control policy, access log and denied-access/transfer tests.
  - When relevant: Only for exceptional special-category personal-data processing specifically for bias detection/correction; not general PII erasure.

## article-4a-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-4a)

- **article_4a_2_evidence** (developer, evidence): For this exceptional bias-audit use outside the high-risk provider case, what establishes strict necessity and application of the referenced safeguards?
  - Evidence to inspect: Purpose and necessity record plus safeguard implementation evidence.
  - When relevant: Only for exceptional special-category personal-data processing specifically for bias detection/correction; not general PII erasure.

## article-6-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_1_evidence** (developer, evidence): Which documented product-safety role and third-party assessment requirement determine whether this system falls within the product-related classification route?
  - Evidence to inspect: Product classification assessment, safety-function mapping and assessment route.
  - When relevant: Only when establishing the classification route for the actual intended deployment; code alone does not decide classification.

## article-6-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_2_evidence** (developer, evidence): Which specific Annex III use case does the intended deployment match, and what product facts support that mapping?
  - Evidence to inspect: Intended-use record and reviewed Annex III mapping.
  - When relevant: Only when establishing the classification route for the actual intended deployment; code alone does not decide classification.

## article-6-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_3_evidence** (developer, evidence): If a classification exception is relied on, what evidence supports its exact condition and the assessment of decision influence and profiling?
  - Evidence to inspect: Documented exception rationale, decision-impact assessment and profiling analysis.
  - When relevant: Only when establishing the classification route for the actual intended deployment; code alone does not decide classification.

## article-6-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_4_evidence** (developer, evidence): Where is the pre-deployment classification assessment recorded, and who maintains the associated registration and authority-request evidence?
  - Evidence to inspect: Dated classification assessment, registration record and accountable owner.
  - When relevant: Only when establishing the classification route for the actual intended deployment; code alone does not decide classification.

## article-6-5

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_5_evidence** (regulatory_maintenance, evidence): Which published implementation guidance was checked against this corpus revision, and what source/version record supports that check?
  - Evidence to inspect: Official guidance reference, retrieval date and corpus impact review.
  - When relevant: For corpus and regulatory-maintenance reviewers checking official source changes; not a developer implementation duty.

## article-6-6

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_6_evidence** (regulatory_maintenance, evidence): Who monitors delegated changes that add or modify classification conditions, and which documented event triggers reassessment of affected systems?
  - Evidence to inspect: Official-source watch record and classification reassessment procedure.
  - When relevant: For corpus and regulatory-maintenance reviewers checking official source changes; not a developer implementation duty.

## article-6-7

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_7_evidence** (regulatory_maintenance, evidence): How would removal of a classification condition be detected and linked to reviews that previously relied on it?
  - Evidence to inspect: Condition-to-review dependency record and amendment impact workflow.
  - When relevant: For corpus and regulatory-maintenance reviewers checking official source changes; not a developer implementation duty.

## article-6-8

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)

- **article_6_8_evidence** (regulatory_maintenance, evidence): When classification conditions change, who checks consistency with the referenced protections and use-case amendments before updating review rules?
  - Evidence to inspect: Regulatory change review and rule-version approval record.
  - When relevant: For corpus and regulatory-maintenance reviewers checking official source changes; not a developer implementation duty.

## article-8-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-8)

- **article_8_1_evidence** (developer, evidence): How are the assessed requirements tied to this system's intended purpose, current technical choices and risk-management findings?
  - Evidence to inspect: Purpose-to-control matrix, engineering rationale and risk register links.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-8-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-8)

- **article_8_2_evidence** (developer, evidence): For AI embedded in a regulated product, where are the AI and product requirements reconciled so tests and documentation do not leave gaps?
  - Evidence to inspect: Integrated requirements matrix and product/AI assessment documentation.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_1_evidence** (developer, evidence): Who owns the risk-management record, when was it last reviewed, and can a developer trace an unresolved risk to a release decision?
  - Evidence to inspect: Risk register, named owner, review history and release gate.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **risk_lifecycle** (developer, context): Where are risks from intended use and foreseeable misuse recorded, evaluated and reviewed over time?
- **article_9_2_evidence** (developer, evidence): Which foreseeable misuse scenarios were tested, and how did observed deployment or monitoring evidence change the recorded risks and mitigations?
  - Evidence to inspect: Misuse test cases, monitoring review and updated mitigation record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_3_evidence** (developer, evidence): Which identified risks can be mitigated through design or technical information, and where are the limits of those mitigations documented?
  - Evidence to inspect: Design-risk analysis, mitigation rationale and residual-risk record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_4_evidence** (developer, evidence): Which combined-control test checks that a mitigation does not introduce a new safety or rights-related failure elsewhere in this workflow?
  - Evidence to inspect: Control interaction analysis and combined-system test report.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-5

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_5_evidence** (developer, evidence): Which residual risks were accepted, by whom and on what evidence, after design changes and other mitigations were evaluated?
  - Evidence to inspect: Residual-risk assessment, design alternatives and acceptance sign-off.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-6

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_6_evidence** (developer, evidence): Which tests demonstrate the intended behaviour and the effectiveness of each risk mitigation for the actual use case?
  - Evidence to inspect: Purpose-specific test plan and mitigation verification results.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-7

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_7_evidence** (developer, evidence): If testing occurs in real-world conditions, what documented review identifies the additional rules and safeguards that must be checked?
  - Evidence to inspect: Real-world test protocol and specialist review of applicable safeguards.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-8

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **risk_test** (developer, context): What predefined metrics and thresholds are used to test the model before deployment?
- **article_9_8_evidence** (developer, evidence): Were release metrics and thresholds fixed before testing, and where is the unchanged test configuration linked to the deployment decision?
  - Evidence to inspect: Timestamped acceptance criteria, test configuration and release record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-9

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_9_evidence** (developer, evidence): Could children or other vulnerable groups be affected, and what changes to the risk assessment follow from their specific exposure?
  - Evidence to inspect: Affected-group assessment, targeted test cases and mitigation decisions.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-9-10

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)

- **article_9_10_evidence** (developer, evidence): If existing sector risk processes are reused, which mapping shows that no AI-specific lifecycle risk is omitted?
  - Evidence to inspect: Sector/AI risk-process mapping and gap review.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-10-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-10)

- **article_10_1_evidence** (developer, evidence): Which training, validation and test datasets were actually used, and where is their quality assessment linked to the resulting model version?
  - Evidence to inspect: Dataset-version manifest, quality reports and model lineage.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-10-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-10)

- **data_origin** (developer, context): Where did the training data come from, how were labels checked, and what cleaning or exclusion steps were documented?
- **data_bias** (developer, context): Which bias tests and mitigation steps were performed on the training and validation data for the affected applicant groups?
- **article_10_2_evidence** (developer, evidence): Can you trace a sampled training label to its source and corrections, and show why known collection biases were addressed for this use?
  - Evidence to inspect: Source lineage, label audit, cleaning log and bias-mitigation evidence.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **labels_historical_bias** (developer, evidence): Do historical hiring labels encode earlier selection patterns, and what measured checks distinguish those patterns from suitability for the intended role?
  - Evidence to inspect: Label provenance, sampling review and bias-test/mitigation results.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **label_disagreement** (developer, evidence): Where annotators disagree, who resolves the label and what audit measures the resulting label consistency for the intended use?
  - Evidence to inspect: Annotation protocol, disagreement sample and adjudication records.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **data_preparation_exclusions** (developer, evidence): Which applicants disappear after cleaning or missing-value filtering, and how did that change the composition of the training population?
  - Evidence to inspect: Before/after dataset counts, exclusion reasons and population breakdown.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **personal_data_original_purpose** (developer, evidence): Which personal-data fields enter training, what was their original collection purpose, and where is the choice to reuse them documented?
  - Evidence to inspect: Field inventory, source-collection record and reuse rationale.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-10-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-10)

- **data_quality** (developer, context): How were missing values, label errors and representativeness checked for the intended applicant population?
- **article_10_3_evidence** (developer, evidence): Which affected groups, missing values and label errors were measured, and what evidence supports the dataset's representativeness for the intended task?
  - Evidence to inspect: Population comparison, missingness and label-error audit, subgroup counts.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **minority_sample_uncertainty** (developer, evidence): Which applicant groups have too few or unrepresentative examples to support the claimed evaluation, and how are those limitations documented?
  - Evidence to inspect: Per-group counts, population comparison and uncertainty/limitation report.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-10-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-10)

- **data_context** (developer, context): Which deployment population and environment were used when selecting the training and evaluation data?
- **article_10_4_evidence** (developer, evidence): How do evaluation data reflect the geography and operating conditions of deployment, and what evidence covers conditions absent from training?
  - Evidence to inspect: Deployment/data comparison and out-of-distribution evaluation report.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-10-6

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-10)

- **article_10_6_evidence** (developer, evidence): If this system does not train an AI model, which testing datasets are still subject to the referenced quality checks and why?
  - Evidence to inspect: Technique assessment, testing-data inventory and quality evidence.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-11-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-11)

- **documentation** (developer, context): Where are the model version, intended use, training choices and evaluation evidence documented?
- **article_11_1_evidence** (developer, evidence): Can a reviewer reproduce the documented model, data and evaluation state for the exact version proposed for release?
  - Evidence to inspect: Versioned technical file, model/data hashes and release checklist.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-11-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-11)

- **article_11_2_evidence** (developer, evidence): For an AI system within a regulated product, where is the single documentation set that covers both AI and product information requirements?
  - Evidence to inspect: Integrated technical file and cross-referenced requirements checklist.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-11-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-11)

- **article_11_3_evidence** (regulatory_maintenance, evidence): How are amendments to technical-documentation requirements detected and propagated into the maintained corpus and documentation checklist?
  - Evidence to inspect: Official amendment source, checklist version and impact-review record.
  - When relevant: For corpus and regulatory-maintenance reviewers checking official source changes; not a developer implementation duty.

## article-12-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12)

- **logging** (developer, context): Which model version, input reference, score and reviewer action are logged for each decision?
- **article_12_1_evidence** (developer, evidence): Can an operator reconstruct a disputed prediction from recorded events without relying on an engineer's memory or rerunning changed code?
  - Evidence to inspect: Sample event log with model version, timestamps and decision linkage.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-12-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12)

- **article_12_2_evidence** (developer, evidence): Which logged events reveal a risk situation, substantial modification or monitoring problem, and has their capture been tested?
  - Evidence to inspect: Event taxonomy, risk-trigger mapping and traceability test results.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-12-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12)

- **article_12_3_evidence** (developer, evidence): For remote biometric identification, can a reviewed log link the use period, reference database, matched input and responsible human verifiers?
  - Evidence to inspect: Scoped biometric audit log and verification trace.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-13-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-13)

- **instructions** (developer, context): What limitations and instructions do the people interpreting these scores receive?
- **article_13_1_evidence** (developer, evidence): What lets the deployer distinguish a reliable prediction from an unsupported or out-of-scope result before acting on it?
  - Evidence to inspect: Output interpretation guide, limitation display and operator usability test.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-13-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-13)

- **article_13_2_evidence** (developer, evidence): Have representative operators tested whether the supplied instructions are clear, accessible and correct for the deployed workflow?
  - Evidence to inspect: Versioned instructions and operator comprehension/accessibility review.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-13-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-13)

- **article_13_3_evidence** (developer, evidence): Which performance limits, input assumptions, oversight actions and maintenance conditions are missing from the instructions given to operators?
  - Evidence to inspect: Instruction completeness review linked to validation and oversight evidence.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-14-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14)

- **article_14_1_evidence** (developer, evidence): Can the assigned reviewer actually observe and intervene in this workflow before the AI output causes an irreversible action?
  - Evidence to inspect: Interface walkthrough and intervention timing test.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-14-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14)

- **article_14_2_evidence** (developer, evidence): Which residual-risk scenario requires human intervention, and what evidence shows the reviewer can recognise and respond to it?
  - Evidence to inspect: Residual-risk scenario, operator exercise and response assessment.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-14-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14)

- **article_14_3_evidence** (developer, evidence): Which oversight controls are built into the product and which depend on the deployer, and who verifies that the latter exist before use?
  - Evidence to inspect: Provider/deployer responsibility matrix and deployment acceptance record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-14-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14)

- **oversight_override** (developer, context): Who can inspect and override the shortlist, and how can they pause or reverse an automated decision?
- **article_14_4_evidence** (developer, evidence): When did a reviewer last override or stop a model decision in a test, and what evidence shows the intervention changed the downstream outcome?
  - Evidence to inspect: Override/stop test trace, reviewer permissions and downstream state check.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **oversight_automation_bias** (developer, evidence): What operator exercise checks that a reviewer questions a confident but wrong model result rather than routinely accepting it?
  - Evidence to inspect: Operator exercise with misleading outputs and observed reviewer actions.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **oversight_stop_state** (developer, evidence): When an operator stops or reverses this workflow, what downstream actions are prevented and what test verifies that the stop is safe?
  - Evidence to inspect: End-to-end stop/reversal test and downstream state inspection.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-14-5

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14)

- **article_14_5_evidence** (developer, evidence): Where the biometric two-person verification rule is relevant, how is independent confirmation enforced before action, and what supports any claimed exception?
  - Evidence to inspect: Verification workflow, independent approvals and scoped exception assessment.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-15-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-15)

- **accuracy_validation** (developer, context): Which held-out evaluation results and acceptance thresholds support using these scores for the intended hiring task?
- **article_15_1_evidence** (developer, evidence): Which failure modes and subgroup error rates remain hidden by the headline accuracy metric, and which acceptance criteria bound their impact?
  - Evidence to inspect: Held-out subgroup evaluation, robustness tests and acceptance criteria.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **performance_error_asymmetry** (developer, evidence): Which false-positive and false-negative outcomes cause different harms here, and how were acceptance criteria chosen around those differences?
  - Evidence to inspect: Error-type analysis, separate evaluation rates and acceptance rationale.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **performance_shift_alert** (developer, evidence): How are changes in accuracy or robustness detected after deployment, and what measured threshold makes the responsible owner investigate?
  - Evidence to inspect: Baseline metrics, change-detection thresholds and investigation record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-15-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-15)

- **article_15_2_evidence** (regulatory_maintenance, evidence): Which official benchmark or measurement-methodology developments were reviewed, and how are changes assessed before revising evaluation rules?
  - Evidence to inspect: Benchmark provenance, methodology version and review record.
  - When relevant: For corpus and regulatory-maintenance reviewers checking official source changes; not a developer implementation duty.

## article-15-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-15)

- **accuracy_metrics** (developer, context): Which accuracy metrics and limitations are communicated to the people using these model outputs?
- **article_15_3_evidence** (developer, evidence): Do the accuracy metrics in the user instructions match results for the released model version and stated operating conditions?
  - Evidence to inspect: Published metric specification, versioned evaluation and instruction comparison.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-15-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-15)

- **article_15_4_evidence** (developer, evidence): How does the system behave with missing, contradictory or shifted inputs, and how are feedback loops from its own outputs detected?
  - Evidence to inspect: Fault-injection, distribution-shift and feedback-loop test records.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **robustness_feedback_loop** (developer, evidence): Could model-selected outcomes become future training inputs, and what test detects a feedback loop that amplifies earlier errors or bias?
  - Evidence to inspect: Data-feedback map and iterative retraining/feedback simulation.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-15-5

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-15)

- **model_security** (developer, context): How are loaded model artifacts and prediction inputs checked for tampering or poisoning?
- **article_15_5_evidence** (developer, evidence): Which tests cover poisoned data or models, adversarial inputs and confidentiality attacks relevant to this system's actual interfaces?
  - Evidence to inspect: Threat model, artifact-integrity checks and adversarial/security test report.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **security_model_artifact** (developer, evidence): Before loading a model, what verifies artifact origin and integrity, and what happens when that check fails?
  - Evidence to inspect: Artifact signature/hash verification and failed-verification test.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-16

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-16)

- **provider_role** (developer, context): Who provides this system under their name and is responsible for its development and documentation?
- **article_16_evidence** (developer, evidence): Who owns the provider responsibilities for this exact release, and where can engineering hand off unresolved conformity or corrective-action evidence?
  - Evidence to inspect: Provider responsibility matrix, release evidence and corrective-action owner.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_1_evidence** (developer, evidence): Which deployment controls prevent operators from using the system outside the instructions supplied for this version?
  - Evidence to inspect: Deployment configuration, instruction mapping and misuse checks.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **deployer_oversight** (developer, context): Who operates this system and assigns trained people with authority to review its decisions?
- **article_26_2_evidence** (developer, evidence): Which named role has the competence, time and authority to challenge a model output, and how was that capability exercised?
  - Evidence to inspect: Role assignment, training evidence and intervention exercise record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_3_evidence** (developer, evidence): Where is the boundary between the provider's oversight design and the deployer's staffing or operating arrangements documented?
  - Evidence to inspect: Oversight responsibility agreement and operating procedure.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **deployer_input** (developer, context): Who controls the live input data and checks that it represents the intended population?
- **article_26_4_evidence** (developer, evidence): Which live input-quality checks does the deployer control, and what happens when the incoming population differs from the intended one?
  - Evidence to inspect: Input-quality monitor, population comparison and escalation runbook.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-5

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_5_evidence** (developer, evidence): Which monitoring signal makes an operator suspend use, who is notified, and when was that incident path last rehearsed?
  - Evidence to inspect: Operational thresholds, notification tree and incident exercise record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.
- **incident_stop_rehearsal** (developer, evidence): Can the operating team demonstrate a recent exercise that detected a risky output, suspended use and reached the correct notification owner?
  - Evidence to inspect: Dated incident exercise, suspension trace and notification log.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-6

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_6_evidence** (developer, evidence): How are logs under the deployer's control retained for the applicable period and retrieved, and who approves and verifies the retention policy?
  - Evidence to inspect: Scoped retention assessment, configuration, retrieval test and approval record.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-7

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_7_evidence** (developer, evidence): For workplace use, what record shows the affected workers and their representatives were informed before this system was introduced?
  - Evidence to inspect: Workplace rollout timeline and notification records.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-8

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_8_evidence** (developer, evidence): For a public-sector deployment, who verifies the relevant registration before use and blocks rollout when the check fails?
  - Evidence to inspect: Registration-check record and failed-check deployment gate test.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-9

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_9_evidence** (developer, evidence): Where a data-protection impact assessment is required, which provider information is supplied to its responsible reviewer and kept current?
  - Evidence to inspect: Assessment handoff record, provider information version and reviewer owner.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-10

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_10_evidence** (developer, evidence): For targeted post-remote biometric law-enforcement use, how are authorisation, scope limits, rejected-request deletion and human decision safeguards enforced?
  - Evidence to inspect: Scoped authorisation workflow, use records, deletion checks and human approvals.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-11

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **affected_people_notice** (developer, context): How are people informed that this system contributes to decisions affecting them?
- **article_26_11_evidence** (developer, evidence): How can an affected person learn that AI contributed to their decision, and which deployed touchpoint delivers that notice?
  - Evidence to inspect: Decision-notice copy, delivery trace and accessibility check.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-26-12

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)

- **article_26_12_evidence** (developer, evidence): Who can retrieve the relevant operating records for a competent-authority request, and has that retrieval path been rehearsed?
  - Evidence to inspect: Authority-request runbook, record inventory and retrieval exercise.
  - When relevant: Only for the relevant high-risk-system context and responsible actor; do not infer classification or actor role from a code name.

## article-50-1

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

- **chatbot_notice** (developer, context): Where are customers told they are interacting with AI before the first reply?
- **chatbot_actor_role** (developer, context): Do you provide this chatbot under your own name, or deploy another provider's system?
- **article_50_1_evidence** (developer, evidence): Can a new user recognise AI interaction before the first reply, and what evidence supports any claim that a separate notice is unnecessary?
  - Evidence to inspect: First-interaction UI capture, user test and notice-scope assessment.
  - When relevant: Only when the specific interaction, generated content or disclosure situation in this paragraph is evidenced; review its exceptions and actor role.

## article-50-2

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

- **synthetic_content_marking** (developer, context): How are synthetic outputs marked as AI-generated and detected by downstream users?
- **synthetic_content_role** (developer, context): Which content types are generated, and what is your provider or deployer role?
- **article_50_2_evidence** (developer, evidence): Does the machine-readable AI marking survive the real export and downstream processing path, and what detection test demonstrates that?
  - Evidence to inspect: Marked output samples, transformation tests and detector results.
  - When relevant: Only when the specific interaction, generated content or disclosure situation in this paragraph is evidenced; review its exceptions and actor role.

## article-50-3

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

- **article_50_3_evidence** (developer, evidence): For emotion recognition or biometric categorisation, where do exposed people receive an operation notice and who reviews the accompanying personal-data processing?
  - Evidence to inspect: Deployment notice, delivery evidence and specialist processing review.
  - When relevant: Only when the specific interaction, generated content or disclosure situation in this paragraph is evidenced; review its exceptions and actor role.

## article-50-4

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

- **deepfake_notice** (developer, context): How are viewers informed when this output is a deepfake rather than authentic content?
- **article_50_4_evidence** (developer, evidence): Which generated media or public-interest text reaches an audience, and what documented disclosure or scoped exception applies to that publication path?
  - Evidence to inspect: Publication flow, disclosure examples and editorial/exception assessment.
  - When relevant: Only when the specific interaction, generated content or disclosure situation in this paragraph is evidenced; review its exceptions and actor role.

## article-50-5

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

- **notice_timing** (developer, context): When and in what accessible form is the AI disclosure shown to the affected person?
- **article_50_5_evidence** (developer, evidence): Can users encounter the first AI output before its notice, or miss the notice because of accessibility barriers?
  - Evidence to inspect: First-exposure timing test and assistive-technology accessibility results.
  - When relevant: Only when the specific interaction, generated content or disclosure situation in this paragraph is evidenced; review its exceptions and actor role.

## article-50-6

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

- **article_50_6_evidence** (developer, evidence): Which review ensures that transparency notices are not treated as replacing separate high-risk-system requirements?
  - Evidence to inspect: Separate requirement checklists and scoped review sign-off.
  - When relevant: Only when the specific interaction, generated content or disclosure situation in this paragraph is evidenced; review its exceptions and actor role.

## article-50-7

[Official source](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

- **article_50_7_evidence** (regulatory_maintenance, evidence): Which officially assessed code or common rule is relied on for synthetic-content marking, and where is its version and status checked?
  - Evidence to inspect: Official code/rule reference and source-status review record.
  - When relevant: For corpus and regulatory-maintenance reviewers checking official source changes; not a developer implementation duty.

## General context questions

- **general_decision_context**: Which real decisions use these predictions, who is affected, and where will the system be deployed?
- **general_model_purpose**: Is this an AI model or a deterministic transformation, and what is the intended use of its predictions?
