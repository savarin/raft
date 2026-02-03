# Scene 5: Log Replication
# Duration: 50 seconds

from manim import *

# Color palette
LEADER_COLOR = "#3498db"
FOLLOWER_COLOR = "#95a5a6"
COMMITTED_COLOR = "#2ecc71"
FAILED_COLOR = "#e74c3c"
BG_COLOR = "#1a1a2e"


class ReplicationScene(Scene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # Create three servers
        s1 = self.create_server("S1", LEFT * 4 + UP * 1)
        s2 = self.create_server("S2", RIGHT * 1 + UP * 1)
        s3 = self.create_server("S3", RIGHT * 4 + UP * 1)

        # Labels
        label1 = Text("Leader", font_size=18, color=LEADER_COLOR).next_to(
            s1, DOWN, buff=0.1
        )
        label2 = Text("Follower", font_size=18, color=FOLLOWER_COLOR).next_to(
            s2, DOWN, buff=0.1
        )
        label3 = Text("Follower", font_size=18, color=FOLLOWER_COLOR).next_to(
            s3, DOWN, buff=0.1
        )

        s1[0].set_color(LEADER_COLOR)

        # Log positions
        log1_pos = LEFT * 4 + DOWN * 1.5
        log2_pos = RIGHT * 1 + DOWN * 1.5
        log3_pos = RIGHT * 4 + DOWN * 1.5

        # Initial setup
        self.play(
            FadeIn(s1),
            FadeIn(s2),
            FadeIn(s3),
            FadeIn(label1),
            FadeIn(label2),
            FadeIn(label3),
            run_time=1,
        )

        # Shot 5.1 [6s]: Leader has log entries
        log1 = self.create_log(["A", "B", "C"], log1_pos)
        log1_label = Text("Log:", font_size=16, color=WHITE).next_to(
            log1, UP, buff=0.1
        )

        self.play(FadeIn(log1), FadeIn(log1_label), run_time=2)
        self.wait(4)

        # Shot 5.2 [7s]: Arrow to S2 with entries
        arrow_to_s2 = Arrow(
            s1.get_center() + DOWN * 0.5,
            s2.get_center() + DOWN * 0.5,
            buff=0.5,
            color=LEADER_COLOR,
        )
        append_label = Text("AppendEntries [A,B,C]", font_size=14, color=LEADER_COLOR).next_to(
            arrow_to_s2, UP, buff=0.1
        )

        self.play(Create(arrow_to_s2), FadeIn(append_label), run_time=2)
        self.wait(5)

        # Shot 5.3 [8s]: S2 receives and confirms
        log2 = self.create_log(["A", "B", "C"], log2_pos)
        log2_label = Text("Log:", font_size=16, color=WHITE).next_to(
            log2, UP, buff=0.1
        )
        checkmark = Text("✓", font_size=24, color=COMMITTED_COLOR).next_to(s2, RIGHT)

        self.play(FadeIn(log2), FadeIn(log2_label), run_time=1)
        self.play(FadeIn(checkmark), run_time=1)

        return_arrow = Arrow(
            s2.get_center() + UP * 0.3,
            s1.get_center() + UP * 0.3,
            buff=0.5,
            color=COMMITTED_COLOR,
        )
        success_label = Text("Success", font_size=14, color=COMMITTED_COLOR).next_to(
            return_arrow, UP, buff=0.1
        )
        self.play(Create(return_arrow), FadeIn(success_label), run_time=1)
        self.wait(5)

        # Cleanup
        self.play(
            FadeOut(arrow_to_s2),
            FadeOut(append_label),
            FadeOut(return_arrow),
            FadeOut(success_label),
            FadeOut(checkmark),
            run_time=0.5,
        )

        # Shot 5.4 [6s]: Same for S3
        log3 = self.create_log(["A", "B", "C"], log3_pos)
        log3_label = Text("Log:", font_size=16, color=WHITE).next_to(
            log3, UP, buff=0.1
        )
        checkmark3 = Text("✓", font_size=24, color=COMMITTED_COLOR).next_to(s3, RIGHT)

        self.play(FadeIn(log3), FadeIn(log3_label), run_time=1)
        self.play(FadeIn(checkmark3), run_time=0.5)
        self.wait(4.5)
        self.play(FadeOut(checkmark3), run_time=0.5)

        # Shot 5.5 [8s]: Conflict scenario - S2 has different entry
        conflict_title = Text(
            "What if logs diverge?", font_size=28, color=FAILED_COLOR
        ).to_edge(UP)
        self.play(FadeIn(conflict_title), run_time=1)

        # Change S2's log to show conflict
        log2_conflict = self.create_log(["A", "B", "X"], log2_pos, conflict_idx=2)
        self.play(Transform(log2, log2_conflict), run_time=1)

        # Highlight the mismatch
        mismatch_circle = Circle(radius=0.35, color=FAILED_COLOR, stroke_width=3).move_to(
            log2_pos + RIGHT * 0.8
        )
        self.play(Create(mismatch_circle), run_time=1)
        self.wait(5)

        # Shot 5.6 [8s]: Leader walks backward
        self.play(FadeOut(mismatch_circle), FadeOut(conflict_title), run_time=0.5)

        backtrack_text = Text(
            "Walk backward to find match...", font_size=20, color=LEADER_COLOR
        ).to_edge(UP)
        self.play(FadeIn(backtrack_text), run_time=1)

        # Highlight matching B entries
        match_circle1 = Circle(radius=0.35, color=COMMITTED_COLOR, stroke_width=3).move_to(
            log1_pos + RIGHT * 0.4
        )
        match_circle2 = Circle(radius=0.35, color=COMMITTED_COLOR, stroke_width=3).move_to(
            log2_pos + RIGHT * 0.4
        )

        self.play(Create(match_circle1), Create(match_circle2), run_time=1)

        match_label = Text("Match at B!", font_size=20, color=COMMITTED_COLOR).next_to(
            match_circle2, DOWN, buff=0.3
        )
        self.play(FadeIn(match_label), run_time=1)
        self.wait(5)

        # Shot 5.7 [7s]: Overwrite with correct entry
        self.play(
            FadeOut(match_circle1),
            FadeOut(match_circle2),
            FadeOut(match_label),
            FadeOut(backtrack_text),
            run_time=0.5,
        )

        overwrite_text = Text(
            "Overwrite from match point", font_size=20, color=LEADER_COLOR
        ).to_edge(UP)
        self.play(FadeIn(overwrite_text), run_time=1)

        # Fix S2's log
        log2_fixed = self.create_log(["A", "B", "C"], log2_pos)
        self.play(Transform(log2, log2_fixed), run_time=1)

        # Show all logs aligned
        aligned_text = Text(
            "Logs aligned!", font_size=24, color=COMMITTED_COLOR
        ).to_edge(DOWN)
        self.play(FadeIn(aligned_text), run_time=1)
        self.wait(4)

    def create_server(self, label, position):
        circle = Circle(radius=0.4, color=FOLLOWER_COLOR, fill_opacity=0.3)
        text = Text(label, font_size=20, color=WHITE)
        server = VGroup(circle, text).move_to(position)
        return server

    def create_log(self, entries, position, conflict_idx=None):
        boxes = VGroup()
        for i, entry in enumerate(entries):
            color = FAILED_COLOR if i == conflict_idx else WHITE
            box = Rectangle(width=0.6, height=0.5, color=color, fill_opacity=0.2)
            label = Text(entry, font_size=18, color=color)
            entry_group = VGroup(box, label)
            boxes.add(entry_group)
        boxes.arrange(RIGHT, buff=0.1)
        boxes.move_to(position)
        return boxes
