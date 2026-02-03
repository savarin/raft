# Scene 7: Putting It Together
# Duration: 10 seconds

from manim import *

# Color palette
LEADER_COLOR = "#3498db"
FOLLOWER_COLOR = "#95a5a6"
COMMITTED_COLOR = "#2ecc71"
CANDIDATE_COLOR = "#f1c40f"
BG_COLOR = "#1a1a2e"


class RecapScene(Scene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("Raft Consensus", font_size=42, color=WHITE).to_edge(UP)
        self.play(Write(title), run_time=1)

        # Three columns for the rules
        col1 = VGroup(
            Text("Terms", font_size=28, color=LEADER_COLOR),
            Text("↓", font_size=24, color=WHITE),
            Text("Prevent\nsplit-brain", font_size=20, color=WHITE, line_spacing=1),
        ).arrange(DOWN, buff=0.2)

        col2 = VGroup(
            Text("Continuity", font_size=28, color=CANDIDATE_COLOR),
            Text("↓", font_size=24, color=WHITE),
            Text("Prevent\ndivergence", font_size=20, color=WHITE, line_spacing=1),
        ).arrange(DOWN, buff=0.2)

        col3 = VGroup(
            Text("Majority", font_size=28, color=COMMITTED_COLOR),
            Text("↓", font_size=24, color=WHITE),
            Text("Make it\nreal", font_size=20, color=WHITE, line_spacing=1),
        ).arrange(DOWN, buff=0.2)

        columns = VGroup(col1, col2, col3).arrange(RIGHT, buff=1.5).shift(UP * 0.5)

        # Animate columns appearing
        self.play(FadeIn(col1), run_time=1.5)
        self.play(FadeIn(col2), run_time=1.5)
        self.play(FadeIn(col3), run_time=1.5)

        # Three stable servers at bottom
        s1 = self.create_server("S1", LEFT * 2.5 + DOWN * 2.5, LEADER_COLOR)
        s2 = self.create_server("S2", ORIGIN + DOWN * 2.5, FOLLOWER_COLOR)
        s3 = self.create_server("S3", RIGHT * 2.5 + DOWN * 2.5, FOLLOWER_COLOR)

        checkmark = Text("✓", font_size=24, color=COMMITTED_COLOR).shift(DOWN * 3.3)

        self.play(FadeIn(s1), FadeIn(s2), FadeIn(s3), run_time=1)
        self.play(FadeIn(checkmark), run_time=0.5)
        self.wait(3)

    def create_server(self, label, position, color):
        circle = Circle(radius=0.4, color=color, fill_opacity=0.3)
        text = Text(label, font_size=18, color=WHITE)
        server = VGroup(circle, text).move_to(position)
        return server
