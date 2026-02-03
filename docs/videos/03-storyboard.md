# Storyboard: Raft Consensus Overview

**Target duration: 180 seconds**
**Narration pace: ~2.5 words/second (150 words/minute)**

---

## Scene 1: Hook — The Problem
**Total duration: 15s**

### Shot 1.1 [4s]
- **Visual:** Three circles (blue, green, orange) arranged in triangle, labeled S1, S2, S3
- **Animation:** FadeIn nodes simultaneously
- **Narration:** "Three servers need to stay in sync." [7 words ≈ 3s + 1s pause]

### Shot 1.2 [5s]
- **Visual:** S3 (orange) dims, gets X overlay, connection lines to it turn dashed
- **Animation:** FadeOut color, Create X mark
- **Narration:** "But servers crash. Messages get lost." [7 words ≈ 3s + 2s pause]

### Shot 1.3 [6s]
- **Visual:** Question mark appears above remaining S1 and S2, both show "???" state
- **Animation:** FadeIn question marks, nodes pulse with uncertainty
- **Narration:** "How do the survivors agree on what happened?" [8 words ≈ 3s + 3s pause]

---

## Scene 2: The Three Rules
**Total duration: 10s**

### Shot 2.1 [10s]
- **Visual:** Three text lines appear stacked:
  1. "Higher terms win"
  2. "Continuity checks"
  3. "Majority decides"
- **Animation:** Write each line sequentially (2s each), then highlight all (2s pause)
- **Narration:** "Raft solves this with three rules. Higher terms win. Continuity checks. Majority decides." [15 words ≈ 6s + 4s pause]

---

## Scene 3: Roles and Terms
**Total duration: 25s**

### Shot 3.1 [6s]
- **Visual:** Three nodes reappear (all healthy), each labeled "Follower", term counter shows "term: 0"
- **Animation:** FadeIn nodes, Write "Follower" labels
- **Narration:** "Every server starts as a Follower, tracking the current term." [10 words ≈ 4s + 2s pause]

### Shot 3.2 [7s]
- **Visual:** S1 gets highlighted border, label changes to "Leader", crown icon appears
- **Animation:** Transform label, GrowFromCenter crown
- **Narration:** "One server becomes Leader. It coordinates all updates." [8 words ≈ 3s + 4s pause]

### Shot 3.3 [6s]
- **Visual:** Term counter increments from 0 to 1, pulse effect on the number
- **Animation:** Transform counter, Indicate the term number
- **Narration:** "The term number is a logical clock." [7 words ≈ 3s + 3s pause]

### Shot 3.4 [6s]
- **Visual:** Text appears below: "One leader per term — guaranteed"
- **Animation:** Write text with emphasis
- **Narration:** "Raft guarantees: one leader per term. No exceptions." [8 words ≈ 3s + 3s pause]

---

## Scene 4: Leader Election
**Total duration: 45s**

### Shot 4.1 [6s]
- **Visual:** All three nodes as Followers, clock icon appears next to S1
- **Animation:** Create clock, clock hand ticks
- **Narration:** "Followers wait for heartbeats from the Leader." [7 words ≈ 3s + 3s pause]

### Shot 4.2 [6s]
- **Visual:** Clock reaches timeout, alarm effect, S1 border turns yellow
- **Animation:** Clock alarm animation, color change to yellow (Candidate color)
- **Narration:** "If no heartbeat arrives, timeout triggers an election." [8 words ≈ 3s + 3s pause]

### Shot 4.3 [6s]
- **Visual:** S1 label changes to "Candidate", term counter increments to 1
- **Animation:** Transform label, increment counter
- **Narration:** "The server becomes a Candidate and increments its term." [9 words ≈ 4s + 2s pause]

### Shot 4.4 [8s]
- **Visual:** Arrows from S1 to S2 and S3, labeled "RequestVote (term 1)"
- **Animation:** Create arrows with labels, arrows pulse
- **Narration:** "It asks other servers: 'Vote for me in term one.'" [10 words ≈ 4s + 4s pause]

### Shot 4.5 [7s]
- **Visual:** Return arrows from S2 and S3 to S1, labeled "Vote granted", vote counter appears: "2/3"
- **Animation:** Create return arrows, FadeIn vote counter
- **Narration:** "Two votes received. That's a majority." [6 words ≈ 2.5s + 4.5s pause]

### Shot 4.6 [6s]
- **Visual:** S1 label transforms to "Leader", crown appears, color turns blue (Leader color)
- **Animation:** Transform label, GrowFromCenter crown, color shift
- **Narration:** "The Candidate becomes Leader." [4 words ≈ 2s + 4s pause]

### Shot 4.7 [6s]
- **Visual:** Text box appears: "Higher term always wins — stale leaders step down"
- **Animation:** FadeIn text box with border
- **Narration:** "If a leader sees a higher term, it immediately steps down." [11 words ≈ 4.5s + 1.5s pause]

---

## Scene 5: Log Replication
**Total duration: 50s**

### Shot 5.1 [6s]
- **Visual:** S1 (Leader) with log stack: [A, B, C]. S2, S3 (Followers) with empty logs
- **Animation:** FadeIn log rectangles, Write entry labels
- **Narration:** "The Leader maintains a log of commands." [7 words ≈ 3s + 3s pause]

### Shot 5.2 [7s]
- **Visual:** Arrow from S1 to S2 labeled "AppendEntries [A, B, C]"
- **Animation:** Create arrow, entries "fly" along arrow to S2
- **Narration:** "It sends new entries to each Follower." [7 words ≈ 3s + 4s pause]

### Shot 5.3 [8s]
- **Visual:** S2's log fills with [A, B, C], checkmark appears, return arrow labeled "Success"
- **Animation:** Entries appear in S2's log, Create checkmark, return arrow
- **Narration:** "The Follower checks: does this continue my log correctly?" [9 words ≈ 4s + 4s pause]

### Shot 5.4 [6s]
- **Visual:** Same process for S3, all logs now show [A, B, C]
- **Animation:** Repeat entry flow to S3
- **Narration:** "If yes, it appends and confirms." [6 words ≈ 2.5s + 3.5s pause]

### Shot 5.5 [8s]
- **Visual:** New scenario: S2 log shows [A, B, X] (different entry), S1 sends [A, B, C]
- **Animation:** Transform S2's log to show conflict, highlight X vs C mismatch
- **Narration:** "But what if logs diverge? The Follower has a different entry." [11 words ≈ 4.5s + 3.5s pause]

### Shot 5.6 [8s]
- **Visual:** Leader's arrow backs up to "previous entry B", highlights match at B
- **Animation:** Arrow retracts, circle appears around matching B entries
- **Narration:** "The Leader walks backward until finding where logs match." [9 words ≈ 4s + 4s pause]

### Shot 5.7 [7s]
- **Visual:** S2's X entry fades, C entry replaces it, logs now identical
- **Animation:** FadeOut X, FadeIn C, logs align
- **Narration:** "From that point, the Leader's log overwrites." [7 words ≈ 3s + 4s pause]

---

## Scene 6: Commit and Safety
**Total duration: 25s**

### Shot 6.1 [7s]
- **Visual:** Leader (S1) with match_index display: {S2: 2, S3: 2}, threshold line at "majority = 2"
- **Animation:** FadeIn match_index counters, Create threshold line
- **Narration:** "The Leader tracks how far each Follower has replicated." [9 words ≈ 4s + 3s pause]

### Shot 6.2 [8s]
- **Visual:** Both counters reach 3, entries A, B, C get green "committed" highlight
- **Animation:** Counters increment, entries shift to green
- **Narration:** "When a majority confirms, the entry is committed." [8 words ≈ 3s + 5s pause]

### Shot 6.3 [10s]
- **Visual:** Lock icon appears on committed entries, text: "Committed = Permanent"
- **Animation:** GrowFromCenter lock, Write text
- **Narration:** "Once committed, an entry is permanent. It will never be rolled back." [12 words ≈ 5s + 5s pause]

---

## Scene 7: Putting It Together
**Total duration: 10s**

### Shot 7.1 [10s]
- **Visual:** Three-column summary:
  - Column 1: "Terms" with arrow icon → "Prevent split-brain"
  - Column 2: "Continuity" with chain icon → "Prevent divergence"
  - Column 3: "Majority" with group icon → "Make it real"
- **Animation:** FadeIn columns sequentially (2s each), all nodes show stable state below (4s)
- **Narration:** "Terms prevent two leaders. Continuity prevents bad data. Majority makes consensus real." [12 words ≈ 5s + 5s pause]

---

## Timing Verification

| Scene | Planned | Shot Total | Narration Words |
|-------|---------|------------|-----------------|
| 1. Hook | 15s | 15s | 22 words (≈9s) ✓ |
| 2. Three Rules | 10s | 10s | 15 words (≈6s) ✓ |
| 3. Roles and Terms | 25s | 25s | 33 words (≈13s) ✓ |
| 4. Leader Election | 45s | 45s | 55 words (≈22s) ✓ |
| 5. Log Replication | 50s | 50s | 56 words (≈22s) ✓ |
| 6. Commit and Safety | 25s | 25s | 29 words (≈12s) ✓ |
| 7. Recap | 10s | 10s | 12 words (≈5s) ✓ |
| **Total** | **180s** | **180s** | **222 words** |

**Narration density:** 222 words / 180s = 1.23 words/second (well under 2.5 limit — room for viewer absorption) ✓

---

## Color Palette

- **Leader:** Blue (#3498db)
- **Follower:** Gray (#95a5a6)
- **Candidate:** Yellow (#f1c40f)
- **Committed:** Green (#2ecc71)
- **Failed/Conflict:** Red (#e74c3c)
- **Background:** Dark (#1a1a2e)
- **Text:** White (#ffffff)

## Typography

- **Titles:** Sans-serif, 48pt
- **Labels:** Sans-serif, 32pt
- **Code/Terms:** Monospace, 28pt
