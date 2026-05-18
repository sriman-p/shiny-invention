ReqLens
Dashboard
New Project
Agent Registry
Projects

todo-api
url-shortener
calculator
ReqLens v0.1.0

idle
Home
todo-api
Sweep
Sweep Evaluation
todo-api · compare any provider, model, prompt strategy, and context mode in one matrix.

Saved Sweeps
Reopen a running or completed sweep. Metrics are stored after every completed run.

3cc1f6ed
failed
15/16 metric rows · 5/6/2026, 11:33:10 AM

295e2c33
failed
6/16 metric rows · 5/6/2026, 11:07:03 AM

8a3c92b1
failed
0/16 metric rows · 5/6/2026, 11:04:49 AM

24686e6e
failed
8/16 metric rows · 5/6/2026, 10:47:26 AM

97b3f1cf
failed
3/16 metric rows · 5/6/2026, 9:08:02 AM

366e71cf
cancelled
0/16 metric rows · 5/6/2026, 9:02:40 AM

e512e3b7
failed
8/16 metric rows · 5/6/2026, 8:38:45 AM

d8fb3a51
failed
0/16 metric rows · 5/6/2026, 8:30:07 AM

2eb586bc
failed
1/256 metric rows · 5/6/2026, 7:47:59 AM

8aa0a2a1
cancelled
0/256 metric rows · 5/6/2026, 7:47:29 AM

664999e9
cancelled
0/256 metric rows · 5/6/2026, 7:41:50 AM

9410cc5a
cancelled
0/256 metric rows · 5/6/2026, 7:40:28 AM

35a2805a
failed
0/256 metric rows · 5/6/2026, 7:29:54 AM

d91dcf78
cancelled
0/256 metric rows · 5/6/2026, 7:25:02 AM
Status

failed
Progress

16/16
Elapsed

16m 8s
ETA

complete
Winner

few shot static · full · cursor/composer-2
Overall progress
100%
Lift vs Worst Configuration
Baseline: cursor/composer-2 · few_shot_dynamic · local · quality 95.6%, latency 200592ms, tokens 0.
Winner

cursor/composer-2 · few_shot_static · full

Δ Quality

+0.3%

Δ Traceability

+0.0%

Δ Latency

+23.7%

Δ Tokens

+0.0%

# Configuration	Δ Quality	Δ Trace	Δ Accept	Δ Latency	Δ Tokens

#1	cursor/composer-2 · few_shot_static · full	+0.3%	+0.0%	+0.0%	+23.7%	+0.0%
#2	cursor/composer-2 · few_shot_static · minimal	+0.3%	+0.0%	+0.0%	+15.4%	+0.0%
#3	cursor/composer-2 · few_shot_static · local	+0.3%	+0.0%	+0.0%	-2.9%	+0.0%
#4	cursor/composer-2 · zero_shot · module	+0.3%	+0.0%	+0.0%	-16.6%	+0.0%
#5	cursor/composer-2 · zero_shot · full	+0.3%	+0.0%	+0.0%	-22.8%	+0.0%
#6	cursor/composer-2 · few_shot_dynamic · minimal	+0.3%	+0.0%	+0.0%	-58.8%	+0.0%
#7	cursor/composer-2 · few_shot_dynamic · module	+0.3%	+0.0%	+0.0%	-85.3%	+0.0%
#8	cursor/composer-2 · chain_of_thought · full	+0.2%	+0.0%	+0.0%	+25.4%	+0.0%
#9	cursor/composer-2 · few_shot_dynamic · full	+0.2%	+0.0%	+0.0%	+20.0%	+0.0%
#10	cursor/composer-2 · few_shot_static · module	+0.2%	+0.0%	+0.0%	+15.1%	+0.0%
#11	cursor/composer-2 · chain_of_thought · module	+0.2%	+0.0%	+0.0%	+6.0%	+0.0%
#12	cursor/composer-2 · zero_shot · minimal	+0.2%	+0.0%	+0.0%	+3.9%	+0.0%
#13	cursor/composer-2 · chain_of_thought · minimal	+0.2%	+0.0%	+0.0%	-51.8%	+0.0%
#14	cursor/composer-2 · chain_of_thought · local	+0.0%	+0.0%	+0.0%	+11.1%	+0.0%
Run Queue
16 runs created. Each row links to the run detail page.
1
zero shot · minimal
cursor/composer-2
3ccf37e4
succeeded
2
zero shot · local
cursor/composer-2
17278db7
failed
3
zero shot · module
cursor/composer-2
031e97af
succeeded
4
zero shot · full
cursor/composer-2
d2c27aa5
succeeded
5
chain of thought · minimal
cursor/composer-2
d045b1c4
succeeded
6
chain of thought · local
cursor/composer-2
1beeed00
succeeded
7
chain of thought · module
cursor/composer-2
ca6cd0ff
succeeded
8
chain of thought · full
cursor/composer-2
4f3a1708
succeeded
9
few shot static · minimal
cursor/composer-2
53c04209
succeeded
10
few shot static · local
cursor/composer-2
59e7667a
succeeded
11
few shot static · module
cursor/composer-2
f17956b0
succeeded
12
few shot static · full
cursor/composer-2
d3d71a92
succeeded
13
few shot dynamic · minimal
cursor/composer-2
dfb515ef
succeeded
14
few shot dynamic · local
cursor/composer-2
af25e9ee
succeeded
15
few shot dynamic · module
cursor/composer-2
b9f4349a
succeeded
16
few shot dynamic · full
cursor/composer-2
532f98c3
succeeded
Live Reasoning
Waiting for the next run.
No active run yet.
Event Log
Last 80 SSE events from this sweep (auto-reconnects on transient errors).
Stream closed. Stored outputs and metrics are shown below.
All Configuration Graphs
Color-coded comparison across stored sweep rows. Green is stronger, yellow is middle, red needs attention.
Quality

Static artifact score; generated tests are not executed yet

higher wins
#1 few shot static · full
95.9%
cursor/composer-2
#2 few shot static · minimal
95.9%
cursor/composer-2
#3 few shot static · local
95.9%
cursor/composer-2
#4 zero shot · module
95.9%
cursor/composer-2
#5 zero shot · full
95.9%
cursor/composer-2
#6 few shot dynamic · minimal
95.9%
cursor/composer-2
#7 few shot dynamic · module
95.9%
cursor/composer-2
#8 chain of thought · full
95.8%
cursor/composer-2
#9 few shot dynamic · full
95.8%
cursor/composer-2
#10 few shot static · module
95.8%
cursor/composer-2
#11 chain of thought · module
95.8%
cursor/composer-2
#12 zero shot · minimal
95.8%
cursor/composer-2
#13 chain of thought · minimal
95.8%
cursor/composer-2
#14 chain of thought · local
95.6%
cursor/composer-2
#15 few shot dynamic · local
95.6%
cursor/composer-2
Traceability

Requirements covered or partially covered

higher wins
#1 few shot static · full
100.0%
cursor/composer-2
#2 few shot static · minimal
100.0%
cursor/composer-2
#3 few shot static · local
100.0%
cursor/composer-2
#4 zero shot · module
100.0%
cursor/composer-2
#5 zero shot · full
100.0%
cursor/composer-2
#6 few shot dynamic · minimal
100.0%
cursor/composer-2
#7 few shot dynamic · module
100.0%
cursor/composer-2
#8 chain of thought · full
100.0%
cursor/composer-2
#9 few shot dynamic · full
100.0%
cursor/composer-2
#10 few shot static · module
100.0%
cursor/composer-2
#11 chain of thought · module
100.0%
cursor/composer-2
#12 zero shot · minimal
100.0%
cursor/composer-2
#13 chain of thought · minimal
100.0%
cursor/composer-2
#14 chain of thought · local
100.0%
cursor/composer-2
#15 few shot dynamic · local
100.0%
cursor/composer-2
Strict coverage

Requirements fully covered

higher wins
#1 few shot static · full
100.0%
cursor/composer-2
#2 few shot static · minimal
100.0%
cursor/composer-2
#3 few shot static · local
100.0%
cursor/composer-2
#4 zero shot · module
75.0%
cursor/composer-2
#5 zero shot · full
75.0%
cursor/composer-2
#6 few shot dynamic · minimal
100.0%
cursor/composer-2
#7 few shot dynamic · module
100.0%
cursor/composer-2
#8 chain of thought · full
100.0%
cursor/composer-2
#9 few shot dynamic · full
100.0%
cursor/composer-2
#10 few shot static · module
100.0%
cursor/composer-2
#11 chain of thought · module
100.0%
cursor/composer-2
#12 zero shot · minimal
75.0%
cursor/composer-2
#13 chain of thought · minimal
100.0%
cursor/composer-2
#14 chain of thought · local
100.0%
cursor/composer-2
#15 few shot dynamic · local
75.0%
cursor/composer-2
Critique accept

Model-review decisions marked accept

higher wins
#1 few shot static · full
75.0%
cursor/composer-2
#2 few shot static · minimal
75.0%
cursor/composer-2
#3 few shot static · local
75.0%
cursor/composer-2
#4 zero shot · module
75.0%
cursor/composer-2
#5 zero shot · full
75.0%
cursor/composer-2
#6 few shot dynamic · minimal
75.0%
cursor/composer-2
#7 few shot dynamic · module
75.0%
cursor/composer-2
#8 chain of thought · full
75.0%
cursor/composer-2
#9 few shot dynamic · full
75.0%
cursor/composer-2
#10 few shot static · module
75.0%
cursor/composer-2
#11 chain of thought · module
75.0%
cursor/composer-2
#12 zero shot · minimal
75.0%
cursor/composer-2
#13 chain of thought · minimal
75.0%
cursor/composer-2
#14 chain of thought · local
75.0%
cursor/composer-2
#15 few shot dynamic · local
75.0%
cursor/composer-2
Generated coverage

Parsed requirements with at least one generated test

higher wins
#1 few shot static · full
100.0%
cursor/composer-2
#2 few shot static · minimal
100.0%
cursor/composer-2
#3 few shot static · local
100.0%
cursor/composer-2
#4 zero shot · module
100.0%
cursor/composer-2
#5 zero shot · full
100.0%
cursor/composer-2
#6 few shot dynamic · minimal
100.0%
cursor/composer-2
#7 few shot dynamic · module
100.0%
cursor/composer-2
#8 chain of thought · full
100.0%
cursor/composer-2
#9 few shot dynamic · full
100.0%
cursor/composer-2
#10 few shot static · module
100.0%
cursor/composer-2
#11 chain of thought · module
100.0%
cursor/composer-2
#12 zero shot · minimal
100.0%
cursor/composer-2
#13 chain of thought · minimal
100.0%
cursor/composer-2
#14 chain of thought · local
100.0%
cursor/composer-2
#15 few shot dynamic · local
100.0%
cursor/composer-2
Mapped requirements

Parsed requirements linked to implementation symbols

higher wins
#1 few shot static · full
100.0%
cursor/composer-2
#2 few shot static · minimal
100.0%
cursor/composer-2
#3 few shot static · local
100.0%
cursor/composer-2
#4 zero shot · module
100.0%
cursor/composer-2
#5 zero shot · full
100.0%
cursor/composer-2
#6 few shot dynamic · minimal
100.0%
cursor/composer-2
#7 few shot dynamic · module
100.0%
cursor/composer-2
#8 chain of thought · full
100.0%
cursor/composer-2
#9 few shot dynamic · full
100.0%
cursor/composer-2
#10 few shot static · module
100.0%
cursor/composer-2
#11 chain of thought · module
100.0%
cursor/composer-2
#12 zero shot · minimal
100.0%
cursor/composer-2
#13 chain of thought · minimal
100.0%
cursor/composer-2
#14 chain of thought · local
100.0%
cursor/composer-2
#15 few shot dynamic · local
100.0%
cursor/composer-2
Map confidence

Average requirement-to-symbol confidence

higher wins
#1 few shot static · full
97.0%
cursor/composer-2
#2 few shot static · minimal
95.2%
cursor/composer-2
#3 few shot static · local
95.0%
cursor/composer-2
#4 zero shot · module
98.0%
cursor/composer-2
#5 zero shot · full
98.0%
cursor/composer-2
#6 few shot dynamic · minimal
98.0%
cursor/composer-2
#7 few shot dynamic · module
98.0%
cursor/composer-2
#8 chain of thought · full
97.8%
cursor/composer-2
#9 few shot dynamic · full
98.0%
cursor/composer-2
#10 few shot static · module
95.5%
cursor/composer-2
#11 chain of thought · module
98.0%
cursor/composer-2
#12 zero shot · minimal
98.0%
cursor/composer-2
#13 chain of thought · minimal
97.5%
cursor/composer-2
#14 chain of thought · local
98.0%
cursor/composer-2
#15 few shot dynamic · local
97.5%
cursor/composer-2
FAISS evidence

Evidence snippets attached per mapping

higher wins
#1 few shot static · full
4.0
cursor/composer-2
#2 few shot static · minimal
3.8
cursor/composer-2
#3 few shot static · local
3.8
cursor/composer-2
#4 zero shot · module
1.0
cursor/composer-2
#5 zero shot · full
3.5
cursor/composer-2
#6 few shot dynamic · minimal
3.3
cursor/composer-2
#7 few shot dynamic · module
1.0
cursor/composer-2
#8 chain of thought · full
2.5
cursor/composer-2
#9 few shot dynamic · full
1.3
cursor/composer-2
#10 few shot static · module
3.8
cursor/composer-2
#11 chain of thought · module
2.5
cursor/composer-2
#12 zero shot · minimal
1.0
cursor/composer-2
#13 chain of thought · minimal
1.5
cursor/composer-2
#14 chain of thought · local
2.3
cursor/composer-2
#15 few shot dynamic · local
2.8
cursor/composer-2
Latency

Lower is better

lower wins
#1 few shot static · full
2m 33s
cursor/composer-2
#2 few shot static · minimal
2m 49s
cursor/composer-2
#3 few shot static · local
3m 26s
cursor/composer-2
#4 zero shot · module
3m 53s
cursor/composer-2
#5 zero shot · full
4m 6s
cursor/composer-2
#6 few shot dynamic · minimal
5m 18s
cursor/composer-2
#7 few shot dynamic · module
6m 11s
cursor/composer-2
#8 chain of thought · full
2m 29s
cursor/composer-2
#9 few shot dynamic · full
2m 40s
cursor/composer-2
#10 few shot static · module
2m 50s
cursor/composer-2
#11 chain of thought · module
3m 8s
cursor/composer-2
#12 zero shot · minimal
3m 12s
cursor/composer-2
#13 chain of thought · minimal
5m 4s
cursor/composer-2
#14 chain of thought · local
2m 58s
cursor/composer-2
#15 few shot dynamic · local
3m 20s
cursor/composer-2
Result Summary
Rollup for completed sweep runs.
Metric rows

15

Avg accept

75.0%

Avg time

3m 30s

Rank	Configuration	Quality	Trace	Accept
#1	few shot static · full
cursor/composer-2
95.9%	100.0%	75.0%
#2	few shot static · minimal
cursor/composer-2
95.9%	100.0%	75.0%
#3	few shot static · local
cursor/composer-2
95.9%	100.0%	75.0%
#4	zero shot · module
cursor/composer-2
95.9%	100.0%	75.0%
#5	zero shot · full
cursor/composer-2
95.9%	100.0%	75.0%
#6	few shot dynamic · minimal
cursor/composer-2
95.9%	100.0%	75.0%
#7	few shot dynamic · module
cursor/composer-2
95.9%	100.0%	75.0%
#8	chain of thought · full
cursor/composer-2
95.8%	100.0%	75.0%
#9	few shot dynamic · full
cursor/composer-2
95.8%	100.0%	75.0%
#10	few shot static · module
cursor/composer-2
95.8%	100.0%	75.0%
#11	chain of thought · module
cursor/composer-2
95.8%	100.0%	75.0%
#12	zero shot · minimal
cursor/composer-2
95.8%	100.0%	75.0%
#13	chain of thought · minimal
cursor/composer-2
95.8%	100.0%	75.0%
#14	chain of thought · local
cursor/composer-2
95.6%	100.0%	75.0%
#15	few shot dynamic · local
cursor/composer-2
95.6%	100.0%	75.0%
Detailed Metrics
Stored output and cost indicators for each run.
Run	Reqs	Provider	Model	Tests	Gen cov.	Mapped	Strict	FAISS	Map conf.	Stages	Tokens	Outputs	Latency
d3d71a92	4	cursor	composer-2	4	100.0%	100.0%	100.0%	4.0	97.0%	6/6	0	58.2 KB	2m 33s
53c04209	4	cursor	composer-2	4	100.0%	100.0%	100.0%	3.8	95.2%	6/6	0	56.7 KB	2m 49s
59e7667a	4	cursor	composer-2	4	100.0%	100.0%	100.0%	3.8	95.0%	6/6	0	55.8 KB	3m 26s
031e97af	4	cursor	composer-2	4	100.0%	100.0%	75.0%	1.0	98.0%	6/6	0	61.9 KB	3m 53s
d2c27aa5	4	cursor	composer-2	4	100.0%	100.0%	75.0%	3.5	98.0%	6/6	0	62.7 KB	4m 6s
dfb515ef	4	cursor	composer-2	4	100.0%	100.0%	100.0%	3.3	98.0%	6/6	0	59.2 KB	5m 18s
b9f4349a	4	cursor	composer-2	4	100.0%	100.0%	100.0%	1.0	98.0%	6/6	0	60.1 KB	6m 11s
4f3a1708	4	cursor	composer-2	4	100.0%	100.0%	100.0%	2.5	97.8%	6/6	0	59.6 KB	2m 29s
532f98c3	4	cursor	composer-2	4	100.0%	100.0%	100.0%	1.3	98.0%	6/6	0	60.4 KB	2m 40s
f17956b0	4	cursor	composer-2	4	100.0%	100.0%	100.0%	3.8	95.5%	6/6	0	56.0 KB	2m 50s
ca6cd0ff	4	cursor	composer-2	4	100.0%	100.0%	100.0%	2.5	98.0%	6/6	0	58.0 KB	3m 8s
3ccf37e4	4	cursor	composer-2	4	100.0%	100.0%	75.0%	1.0	98.0%	6/6	0	66.9 KB	3m 12s
d045b1c4	4	cursor	composer-2	4	100.0%	100.0%	100.0%	1.5	97.5%	6/6	0	59.6 KB	5m 4s
1beeed00	4	cursor	composer-2	4	100.0%	100.0%	100.0%	2.3	98.0%	6/6	0	58.6 KB	2m 58s
af25e9ee	4	cursor	composer-2	4	100.0%	100.0%	75.0%	2.8	97.5%	6/6	0	57.9 KB	3m 20s
Statistical Significance
ANOVA shows whether an axis matters; eta-squared and Cohen's d show practical effect magnitude.
Statistical results are partial: 15 of 16 configurations produced reliable metrics.
strategy traceability score

ns
p 1.0000
η² 0.000
negligible
strategy strict coverage score

**
p 0.0014
η² 0.744
large
strategy test pass rate

ns
p 1.0000
η² 0.000
negligible
strategy critique accept rate

ns
p 1.0000
η² 0.000
negligible
strategy quality score

ns
p 0.2049
η² 0.330
large
strategy mapped requirements rate

ns
p 1.0000
η² 0.000
negligible
strategy mapping confidence avg

---

p 0.0001
η² 0.837
large
strategy faiss evidence per mapping

- 

p 0.0372
η² 0.523
large
strategy generation coverage rate

ns
p 1.0000
η² 0.000
negligible
strategy trace matrix completion rate

ns
p 1.0000
η² 0.000
negligible
strategy stage success rate

ns
p 1.0000
η² 0.000
negligible
context traceability score

ns
p 1.0000
η² 0.000
negligible
context strict coverage score

ns
p 0.9956
η² 0.006
negligible
context test pass rate

ns
p 1.0000
η² 0.000
negligible
context critique accept rate

ns
p 1.0000
η² 0.000
negligible
context quality score

ns
p 0.3982
η² 0.227
large
context mapped requirements rate

ns
p 1.0000
η² 0.000
negligible
context mapping confidence avg

ns
p 0.8178
η² 0.078
medium
context faiss evidence per mapping

ns
p 0.7606
η² 0.097
medium
context generation coverage rate

ns
p 1.0000
η² 0.000
negligible
context trace matrix completion rate

ns
p 1.0000
η² 0.000
negligible
context stage success rate

ns
p 1.0000
η² 0.000
negligible
Large Cohen's d comparisons

strategy strict coverage score
chain_of_thought vs few_shot_dynamic
Bonferroni p 1.0000
d=0.82 large
strategy strict coverage score
few_shot_dynamic vs few_shot_static
Bonferroni p 1.0000
d=-0.82 large
strategy strict coverage score
few_shot_dynamic vs zero_shot
Bonferroni p 0.3460
d=2.45 large
strategy mapping confidence avg
chain_of_thought vs few_shot_static
Bonferroni p 0.0880
d=3.73 large
strategy mapping confidence avg
chain_of_thought vs zero_shot
Bonferroni p 1.0000
d=-1.28 large
strategy mapping confidence avg
few_shot_dynamic vs few_shot_static
Bonferroni p 0.0793
d=3.83 large
strategy mapping confidence avg
few_shot_dynamic vs zero_shot
Bonferroni p 1.0000
d=-0.82 large
strategy mapping confidence avg
few_shot_static vs zero_shot
Bonferroni p 0.0853
d=-4.20 large
Statistical Report
Rendered as a Markdown file with Preview selected by default.
statistical-report.md
Preview
Markdown
.md

# Statistical Analysis Report

## Best Configuration

Rank 1: few_shot_static / full with 0.959 quality score, 100.0% traceability, and 75.0% critique accept rate.

## Lift vs Worst Configuration

Baseline: **cursor/composer-2 · few_shot_dynamic · local** — quality 0.956, latency 200592 ms, tokens 0.


| Configuration                                  | ΔQuality | ΔTraceability | ΔAccept | ΔLatency | ΔTokens |
| ---------------------------------------------- | -------- | ------------- | ------- | -------- | ------- |
| cursor/composer-2 · few_shot_static · full     | +0.3%    | +0.0%         | +0.0%   | +23.7%   | +0.0%   |
| cursor/composer-2 · few_shot_static · minimal  | +0.3%    | +0.0%         | +0.0%   | +15.4%   | +0.0%   |
| cursor/composer-2 · few_shot_static · local    | +0.3%    | +0.0%         | +0.0%   | -2.9%    | +0.0%   |
| cursor/composer-2 · zero_shot · module         | +0.3%    | +0.0%         | +0.0%   | -16.6%   | +0.0%   |
| cursor/composer-2 · zero_shot · full           | +0.3%    | +0.0%         | +0.0%   | -22.8%   | +0.0%   |
| cursor/composer-2 · few_shot_dynamic · minimal | +0.3%    | +0.0%         | +0.0%   | -58.8%   | +0.0%   |
| cursor/composer-2 · few_shot_dynamic · module  | +0.3%    | +0.0%         | +0.0%   | -85.3%   | +0.0%   |
| cursor/composer-2 · chain_of_thought · full    | +0.2%    | +0.0%         | +0.0%   | +25.4%   | +0.0%   |
| cursor/composer-2 · few_shot_dynamic · full    | +0.2%    | +0.0%         | +0.0%   | +20.0%   | +0.0%   |
| cursor/composer-2 · few_shot_static · module   | +0.2%    | +0.0%         | +0.0%   | +15.1%   | +0.0%   |
| cursor/composer-2 · chain_of_thought · module  | +0.2%    | +0.0%         | +0.0%   | +6.0%    | +0.0%   |
| cursor/composer-2 · zero_shot · minimal        | +0.2%    | +0.0%         | +0.0%   | +3.9%    | +0.0%   |
| cursor/composer-2 · chain_of_thought · minimal | +0.2%    | +0.0%         | +0.0%   | -51.8%   | +0.0%   |
| cursor/composer-2 · chain_of_thought · local   | +0.0%    | +0.0%         | +0.0%   | +11.1%   | +0.0%   |


## ANOVA Results


| Factor                                | Metric | F-statistic | p-value | Significance | eta-squared | Effect     |
| ------------------------------------- | ------ | ----------- | ------- | ------------ | ----------- | ---------- |
| strategy_traceability_score           | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| strategy_strict_coverage_score        | -      | 10.6741     | 0.0014  | **           | 0.7443      | large      |
| strategy_test_pass_rate               | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| strategy_critique_accept_rate         | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| strategy_quality_score                | -      | 1.8023      | 0.2049  | ns           | 0.3295      | large      |
| strategy_mapped_requirements_rate     | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| strategy_mapping_confidence_avg       | -      | 18.7783     | 0.0001  | ***          | 0.8366      | large      |
| strategy_faiss_evidence_per_mapping   | -      | 4.0175      | 0.0372  | *            | 0.5228      | large      |
| strategy_generation_coverage_rate     | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| strategy_trace_matrix_completion_rate | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| strategy_stage_success_rate           | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| context_traceability_score            | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| context_strict_coverage_score         | -      | 0.0210      | 0.9956  | ns           | 0.0057      | negligible |
| context_test_pass_rate                | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| context_critique_accept_rate          | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| context_quality_score                 | -      | 1.0784      | 0.3982  | ns           | 0.2273      | large      |
| context_mapped_requirements_rate      | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| context_mapping_confidence_avg        | -      | 0.3100      | 0.8178  | ns           | 0.0779      | medium     |
| context_faiss_evidence_per_mapping    | -      | 0.3928      | 0.7606  | ns           | 0.0968      | medium     |
| context_generation_coverage_rate      | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| context_trace_matrix_completion_rate  | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |
| context_stage_success_rate            | -      | 0.0000      | 1.0000  | ns           | 0.0000      | negligible |


## Pairwise Comparisons (Bonferroni-corrected)

### strategy_strict_coverage_score


| Pair                                 | t-statistic | p-value | Significance | Cohen's d | Magnitude  |
| ------------------------------------ | ----------- | ------- | ------------ | --------- | ---------- |
| chain_of_thought vs few_shot_dynamic | 1.0000      | 1.0000  | ns           | 0.8165    | large      |
| chain_of_thought vs few_shot_static  | 0.0000      | 1.0000  | ns           | 0.0000    | negligible |
| chain_of_thought vs zero_shot        | 0.0000      | 0.0000  | ***          | 0.0000    | negligible |
| few_shot_dynamic vs few_shot_static  | -1.0000     | 1.0000  | ns           | -0.8165   | large      |
| few_shot_dynamic vs zero_shot        | 3.0000      | 0.3460  | ns           | 2.4495    | large      |
| few_shot_static vs zero_shot         | 0.0000      | 0.0000  | ***          | 0.0000    | negligible |


### strategy_mapping_confidence_avg


| Pair                                 | t-statistic | p-value | Significance | Cohen's d | Magnitude |
| ------------------------------------ | ----------- | ------- | ------------ | --------- | --------- |
| chain_of_thought vs few_shot_dynamic | -0.3612     | 1.0000  | ns           | -0.2949   | small     |
| chain_of_thought vs few_shot_static  | 4.5707      | 0.0880  | ns           | 3.7320    | large     |
| chain_of_thought vs zero_shot        | -1.5667     | 1.0000  | ns           | -1.2792   | large     |
| few_shot_dynamic vs few_shot_static  | 4.6911      | 0.0793  | ns           | 3.8302    | large     |
| few_shot_dynamic vs zero_shot        | -1.0000     | 1.0000  | ns           | -0.8165   | large     |
| few_shot_static vs zero_shot         | -5.1475     | 0.0853  | ns           | -4.2029   | large     |


### strategy_faiss_evidence_per_mapping


| Pair                                 | t-statistic | p-value | Significance | Cohen's d | Magnitude  |
| ------------------------------------ | ----------- | ------- | ------------ | --------- | ---------- |
| chain_of_thought vs few_shot_dynamic | 0.2078      | 1.0000  | ns           | 0.1696    | negligible |
| chain_of_thought vs few_shot_static  | -6.6398     | 0.0275  | *            | -5.4214   | large      |
| chain_of_thought vs zero_shot        | 0.4088      | 1.0000  | ns           | 0.4014    | small      |
| few_shot_dynamic vs few_shot_static  | -3.1436     | 0.2987  | ns           | -2.5668   | large      |
| few_shot_dynamic vs zero_shot        | 0.2291      | 1.0000  | ns           | 0.2134    | small      |
| few_shot_static vs zero_shot         | 2.3683      | 0.8401  | ns           | 2.3650    | large      |


