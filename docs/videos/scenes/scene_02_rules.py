# Scene 2: The Three Rules
# Duration: 10 seconds

from manim import *

# Color palette
BG_COLOR = "#1a1a2e"
ACCENT_COLOR = "#3498db"


class RulesScene(Scene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # Title
        title = Text("Raft's Three Rules", font_size=42, color=WHITE).to_edge(UP)

        # Three rules
        rule1 = Text("1. Higher terms win", font_size=36, color=WHITE)
        rule2 = Text("2. Continuity checks", font_size=36, color=WHITE)
        rule3 = Text("3. Majority decides", font_size=36, color=WHITE)

        rules = VGroup(rule1, rule2, rule3).arrange(DOWN, buff=0.6)

        # Shot 2.1 [10s]: Reveal rules sequentially
        self.play(Write(title), run_time=1)
        self.play(Write(rule1), run_time=2)
        self.play(Write(rule2), run_time=2)
        self.play(Write(rule3), run_time=2)

        # Highlight all rules
        self.play(
            rule1.animate.set_color(ACCENT_COLOR),
            rule2.animate.set_color(ACCENT_COLOR),
            rule3.animate.set_color(ACCENT_COLOR),
            run_time=1,
        )
        self.wait(2)
