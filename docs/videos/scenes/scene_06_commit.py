# Scene 6: Commit and Safety
# Duration: 25 seconds

from manim import *

# Color palette
LEADER_COLOR = "#3498db"
FOLLOWER_COLOR = "#95a5a6"
COMMITTED_COLOR = "#2ecc71"
BG_COLOR = "#1a1a2e"


class CommitScene(Scene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("When is an entry committed?", font_size=32, color=WHITE).to_edge(
            UP
        )
        self.play(Write(title), run_time=1)

        # Create servers in a row
        s1 = self.create_server("S1\nLeader", LEFT * 4, LEADER_COLOR)
        s2 = self.create_server("S2", ORIGIN, FOLLOWER_COLOR)
        s3 = self.create_server("S3", RIGHT * 4, FOLLOWER_COLOR)

        servers = VGroup(s1, s2, s3)
        self.play(FadeIn(servers), run_time=1)

        # Shot 6.1 [7s]: Match index tracking
        match_title = Text(
            "Leader tracks replication:", font_size=24, color=LEADER_COLOR
        ).shift(DOWN * 1)

        match_s2 = Text("S2: index 2", font_size=20, color=WHITE).shift(
            DOWN * 1.7 + LEFT * 1.5
        )
        match_s3 = Text("S3: index 1", font_size=20, color=WHITE).shift(
            DOWN * 1.7 + RIGHT * 1.5
        )

        threshold = DashedLine(
            LEFT * 3 + DOWN * 2.3, RIGHT * 3 + DOWN * 2.3, color=COMMITTED_COLOR
        )
        threshold_label = Text(
            "majority threshold", font_size=16, color=COMMITTED_COLOR
        ).next_to(threshold, DOWN, buff=0.1)

        self.play(Write(match_title), run_time=1)
        self.play(FadeIn(match_s2), FadeIn(match_s3), run_time=1)
        self.play(Create(threshold), FadeIn(threshold_label), run_time=1)
        self.wait(4)

        # Shot 6.2 [8s]: Both reach majority
        new_match_s2 = Text("S2: index 3 ✓", font_size=20, color=COMMITTED_COLOR).shift(
            DOWN * 1.7 + LEFT * 1.5
        )
        new_match_s3 = Text("S3: index 3 ✓", font_size=20, color=COMMITTED_COLOR).shift(
            DOWN * 1.7 + RIGHT * 1.5
        )

        self.play(Transform(match_s2, new_match_s2), run_time=1)
        self.play(Transform(match_s3, new_match_s3), run_time=1)

        committed_text = Text(
            "Majority confirmed → COMMITTED", font_size=28, color=COMMITTED_COLOR
        ).shift(DOWN * 3)
        self.play(Write(committed_text), run_time=1)
        self.wait(5)

        # Shot 6.3 [10s]: Permanent lock
        self.play(
            FadeOut(match_title),
            FadeOut(match_s2),
            FadeOut(match_s3),
            FadeOut(threshold),
            FadeOut(threshold_label),
            FadeOut(committed_text),
            run_time=1,
        )

        lock = Text("🔒", font_size=48).shift(DOWN * 1.5)
        permanent_text = Text(
            "Committed = Permanent", font_size=36, color=COMMITTED_COLOR
        ).shift(DOWN * 2.5)

        self.play(GrowFromCenter(lock), run_time=1)
        self.play(Write(permanent_text), run_time=1)

        no_rollback = Text(
            "No rollback. Ever.", font_size=28, color=WHITE
        ).shift(DOWN * 3.3)
        self.play(FadeIn(no_rollback), run_time=1)
        self.wait(6)

    def create_server(self, label, position, color):
        circle = Circle(radius=0.5, color=color, fill_opacity=0.3)
        text = Text(label, font_size=18, color=WHITE)
        server = VGroup(circle, text).move_to(position)
        return server
