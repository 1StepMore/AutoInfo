# Superseded-artifact residue cleanup (2026-11-20)

L0 gate run over outputs/capability-matrix/<domain> on 2026-11-20 flagged F1 empty shells.
All four are unreferenced by any current matrix.json row (mapped programmatically against
all 81 rows' artifact fields) — they are failed intermediates from matrix runs 1-3 on
2026-11-18, superseded by run-4 finals after the corpus refresh. Removed so that the
standard L0 gate command (`scripts/quality_gate.py outputs/capability-matrix/<domain>`)
gates exactly the delivered product set. Deletion is runtime-state hygiene only;
matrix.json rows were never hand-edited.

| file | bytes | sha256 |
|---|---|---|
| outputs/capability-matrix/ai-commercial/premium-briefing-markdown-20261118-180212-704428.md | 158 | 77496334ed8b9a1a5865021e64cc5371bb2f0f09a876acc4287116984746f49b |
| outputs/capability-matrix/ai-commercial/premium-briefing-markdown-20261118-183446-054102.md | 158 | 77496334ed8b9a1a5865021e64cc5371bb2f0f09a876acc4287116984746f49b |
| outputs/capability-matrix/medical-research/premium-briefing-markdown-20261118-182628-022796.md | 167 | b03f1b9cc2794ca21776b4b7a830f6f95e934ee27c580f36afc361296a784902 |
| outputs/capability-matrix/medical-research/premium-briefing-markdown-20261118-183903-283387.md | 167 | b03f1b9cc2794ca21776b4b7a830f6f95e934ee27c580f36afc361296a784902 |
| outputs/capability-matrix/ai-commercial/tutorial-markdown-20261118-192922-722903.md | 21864 | 535fe6ac8d717296303019a627a91a78dbc6c3426eedd37271ff85a8d546f625 |

Addendum: the ai-commercial tutorial:markdown row was constrained-regenerated on 2026-11-20
(matrix --force; L0 H2 defect feedback), superseding the 2026-11-18 19:29 artifact above.

Addendum 2 (2026-11-20, new-baseline regen): after rebasing onto main #881 (81/81 L3),
ai-commercial/tutorial:markdown was regenerated once more on the new baseline
(tutorial-markdown-20261119-180800-192971.md). The earlier same-day regen artifact is
superseded runtime residue (unreferenced by any matrix.json row):

| file | bytes | sha256 |
|---|---|---|
| outputs/capability-matrix/ai-commercial/tutorial-markdown-20261119-164439-879676.md | 20694 | 55cc400e548167daebde2fdd31ac819cfac0454671fd73720e44f6d9b33170b9 |

Addendum 3 (2026-11-20, outputs-tree fixture guard): 13 undersized persisted artifacts
(111-167 bytes, 2026-11-17 t9-era residue in outputs/{medical-research,online-education,online-video})
flagged by tests/validation/test_no_fixture_artifacts.py::scan_fixture_artifacts. Deleted:

| file | bytes | sha256 |
|---|---|---|
| outputs/medical-research/premium-briefing-markdown-20261117-052509.md | 167 | 8c4f235eac0bb9149d22d0c14dd37413a2bffb6a34f2030a06fbe82351582759 |
| outputs/medical-research/premium-briefing-markdown-20261117-061406.md | 167 | 8c4f235eac0bb9149d22d0c14dd37413a2bffb6a34f2030a06fbe82351582759 |
| outputs/medical-research/premium-briefing-markdown-20261117-070513.md | 167 | 8c4f235eac0bb9149d22d0c14dd37413a2bffb6a34f2030a06fbe82351582759 |
| outputs/online-education/tutorial-markdown-20261117-044746.md | 115 | 955e38701aa709a92b63f8e45be8a08a0cb1f25be8c7e68f2275d6162c67ca27 |
| outputs/online-education/tutorial-markdown-20261117-045234.md | 115 | 955e38701aa709a92b63f8e45be8a08a0cb1f25be8c7e68f2275d6162c67ca27 |
| outputs/online-education/tutorial-markdown-20261117-052743.md | 115 | 955e38701aa709a92b63f8e45be8a08a0cb1f25be8c7e68f2275d6162c67ca27 |
| outputs/online-education/tutorial-markdown-20261117-061649.md | 115 | 955e38701aa709a92b63f8e45be8a08a0cb1f25be8c7e68f2275d6162c67ca27 |
| outputs/online-education/tutorial-markdown-20261117-070800.md | 115 | 955e38701aa709a92b63f8e45be8a08a0cb1f25be8c7e68f2275d6162c67ca27 |
| outputs/online-video/tutorial-markdown-20261117-044742.md | 111 | f049d94eaa3fa506494833339d127b43f602b56d7948add7102fdb579bb836c3 |
| outputs/online-video/tutorial-markdown-20261117-045230.md | 111 | f049d94eaa3fa506494833339d127b43f602b56d7948add7102fdb579bb836c3 |
| outputs/online-video/tutorial-markdown-20261117-052739.md | 111 | f049d94eaa3fa506494833339d127b43f602b56d7948add7102fdb579bb836c3 |
| outputs/online-video/tutorial-markdown-20261117-061644.md | 111 | f049d94eaa3fa506494833339d127b43f602b56d7948add7102fdb579bb836c3 |
| outputs/online-video/tutorial-markdown-20261117-070755.md | 111 | f049d94eaa3fa506494833339d127b43f602b56d7948add7102fdb579bb836c3 |

Addendum 4 (2026-11-20, aborted enriched-corpus rerun): a language-learning re-run with a
newly added Chinese-market source (sspai) was aborted mid-flight after review showed the
source is off-topic for this English-teaching domain (topics: English Vocabulary / Reading
Comprehension / Listening & Pronunciation). The killed run wrote artifacts but never rows
(the driver writes matrix.json once at the end), so matrix.json was never contaminated.
Orphan artifacts deleted:

| file | bytes | sha256 |
|---|---|---|
| outputs/capability-matrix/language-learning/column-markdown-20261119-181900-231940.md | 22279 | 926db14a6f7550aa99fc1b360d558f44279f74d0436479b31faf05df2bb9dc28 |
| outputs/capability-matrix/language-learning/digest-agent-20261027-093839-644068.json | 22555 | 99a85f8c8b34cf425531eae10ee191fe01b3483f49bfa3a9047149313060df2b |
| outputs/capability-matrix/language-learning/digest-agent-20261116-233738-984807.json | 22953 | 7732c7fc6638aed1d807d3f8c2dc98846a11d116b28cbdf45be5b19b80721220 |
| outputs/capability-matrix/language-learning/digest-agent-20261119-181942-240299.json | 32124 | 942ea192a74aa6388a01b55084f502fa748fe695b2983d1f8b0fe79305a34df1 |
| outputs/capability-matrix/language-learning/digest-audio-20261027-093855-772582.mp3 | 1881792 | 6be0212b27a79b370e64e07a293da6d0863c0490d45b5e3662c267e299add004 |
| outputs/capability-matrix/language-learning/digest-audio-20261116-233817-486567.mp3 | 1877472 | 9efaea86d76b449c9a2d9440d79bee3592474d8f9519c2e8cbf1d36447a7f9cc |
| outputs/capability-matrix/language-learning/digest-audio-20261119-182042-010484.mp3 | 1987632 | 2959f74b0c468a28a3cd8419b8e0a014bbf5fd1e10f1dad0c2d51445aaa97eae |
| outputs/capability-matrix/language-learning/digest-audiobook-20261027-093947-897347.zip | 2219233 | daee224c6f6a4483b49e57253db1b1b4bf1e1ca405591bee711ae8831a626b40 |
| outputs/capability-matrix/language-learning/digest-audiobook-20261116-233921-851627.zip | 2299662 | fcbdd6db9d4b8ca1ab71c8a4de3a6998c9e15fc4bea27df735d2f9a8b2e07cc7 |
| outputs/capability-matrix/language-learning/digest-epub-20261027-093953-000743.epub | 15524 | eadb9690457cd1294c0900a211b90710ff75db26cb7f37cdef2d7ae23ba3d13f |
| outputs/capability-matrix/language-learning/digest-epub-20261116-233934-980343.epub | 31472 | 3fc2675db9c00ceedc147e2dc6811be24ceb6d218eef4c27232b83e3b9bfecb9 |
| outputs/capability-matrix/language-learning/digest-html-20261027-093957-752433.html | 29557 | 429d63c70a226a347371f670a1da2ed747417bf2fd3a7e0087f2595dd98401a7 |
| outputs/capability-matrix/language-learning/digest-html-20261116-233949-510090.html | 30847 | 816e879d6eb30124a10e844844cde13cd2264cf8c0a87def451fded5595ea8e5 |
| outputs/capability-matrix/language-learning/digest-json-20261027-094002-167048.json | 38489 | 57036e5f215464c87c8296ef808f9879e2508b7e2a7a308d3f71b56dec7be86e |
| outputs/capability-matrix/language-learning/digest-json-20261116-234003-517351.json | 40131 | 73c3ce0eff89d2f27299bb182595ed1f2013156ced619b7a83a6d04f016adef4 |
| outputs/capability-matrix/language-learning/digest-markdown-20261027-094006-725691.md | 16851 | 0450c2d436df88b2eeeb5b9f3fef2d0f38518df78f8003094973c7dc4e08a107 |
| outputs/capability-matrix/language-learning/digest-markdown-20261116-234017-209955.md | 17722 | ad0d7f420eb63f405d5810ce3a9d512a564b2dd44ff94f5f5ccb1f8fc335929e |
| outputs/capability-matrix/language-learning/report-agent-20261027-094010-304328.json | 21146 | 9f8ac787cd612d8c97df682755022f320028d099dabf9551a9a747ed8680ff39 |
| outputs/capability-matrix/language-learning/report-agent-20261116-234106-571956.json | 21509 | 3e3a52373535948daee5fb4e75575364dfe45c4a414b05a9cac02dacc34e33ca |
| outputs/capability-matrix/language-learning/report-audio-20261027-094028-759552.mp3 | 1849680 | bdcec7b92544af017047f106f975aca45b0438a099ea51324406ee343f992690 |
| outputs/capability-matrix/language-learning/report-audio-20261116-234207-135161.mp3 | 1851408 | ab4ec3d27dc9a6c7a4b5efdbcc3854e216d1431dc310f644c1795804af4c8924 |
| outputs/capability-matrix/language-learning/report-audiobook-20261027-094105-862021.zip | 5084029 | cc6f6d31fc80829733c5afdd535387d2de68fb51f82807e9c615ea488ed90de8 |
| outputs/capability-matrix/language-learning/report-audiobook-20261116-234357-859847.zip | 5083597 | da001046280604513a447d8f49c0d879567253fc4b7c896fe3a22b42565a97f8 |
| outputs/capability-matrix/language-learning/report-epub-20261027-094109-292661.epub | 9149 | 22d681a07e19948d4fd73513c9cf9c6a214a93bea635204e073218eec16954bf |
| outputs/capability-matrix/language-learning/report-html-20261027-094112-768489.html | 26524 | 019b650b8ff81d6c0175deb4c8e24362e890afd55fe6ef46f980cdf47b7b841e |
| outputs/capability-matrix/language-learning/report-json-20261027-094116-216916.json | 19619 | 8ef9376841983ac5ed4578b8ae8245d9670bced663f013d0fab3bb5f607c5109 |
| outputs/capability-matrix/language-learning/report-markdown-20261027-094119-618662.md | 22491 | d12961d515783d09d882e27ac4c6214779e4a157b9d886375dfc34c6107414a6 |
| outputs/capability-matrix/language-learning/tutorial-agent-20261118-182247-617656.json | 72571 | ecacd4da13c786b7e2f8b60472f4a854537e9b5c1b35501efb633cabb1896da1 |
