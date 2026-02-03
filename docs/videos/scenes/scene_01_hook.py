# Scene 1: Hook — The Problem
# Duration: 15 seconds

from manim import *

# Color palette
LEADER_COLOR = "#3498db"
FOLLOWER_COLOR = "#95a5a6"
CANDIDATE_COLOR = "#f1c40f"
COMMITTED_COLOR = "#2ecc71"
FAILED_COLOR = "#e74c3c"
BG_COLOR = "#1a1a2e"


class HookScene(Scene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # Create three server nodes
        s1 = self.create_server("S1", LEFT * 2.5)
        s2 = self.create_server("S2", RIGHT * 2.5)
        s3 = self.create_server("S3", DOWN * 2.5)

        servers = VGroup(s1, s2, s3)

        # Connection lines
        line1 = Line(s1.get_center(), s2.get_center(), color=WHITE, stroke_width=2)
        line2 = Line(s2.get_center(), s3.get_center(), color=WHITE, stroke_width=2)
        line3 = Line(s3.get_center(), s1.get_center(), color=WHITE, stroke_width=2)
        lines = VGroup(line1, line2, line3)

        # Shot 1.1 [4s]: Three servers appear
        self.play(FadeIn(servers), Create(lines), run_time=2)
        self.wait(2)

        # Shot 1.2 [5s]: S3 crashes
        x_mark = Cross(scale_factor=0.5, color=FAILED_COLOR).move_to(s3.get_center())
        self.play(
            s3[0].animate.set_fill(opacity=0.3),
            s3[1].animate.set_opacity(0.3),
            line2.animate.set_stroke(opacity=0.3),
            line3.animate.set_stroke(opacity=0.3),
            Create(x_mark),
            run_time=2,
        )
        self.wait(3)

        # Shot 1.3 [6s]: Question marks appear
        q1 = Text("???", font_size=28, color=CANDIDATE_COLOR).next_to(s1, UP)
        q2 = Text("???", font_size=28, color=CANDIDATE_COLOR).next_to(s2, UP)
        question = Text(
            "How do the survivors agree?", font_size=36, color=WHITE
        ).to_edge(UP)

        self.play(FadeIn(q1), FadeIn(q2), run_time=1)
        self.play(Write(question), run_time=2)
        self.wait(3)

    def create_server(self, label, position):
        circle = Circle(radius=0.6, color=FOLLOWER_COLOR, fill_opacity=0.3)
        text = Text(label, font_size=28, color=WHITE)
        server = VGroup(circle, text).move_to(position)
        return server
