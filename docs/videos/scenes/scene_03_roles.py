# Scene 3: Roles and Terms
# Duration: 25 seconds

from manim import *

# Color palette
LEADER_COLOR = "#3498db"
FOLLOWER_COLOR = "#95a5a6"
BG_COLOR = "#1a1a2e"


class RolesScene(Scene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # Create three server nodes
        s1 = self.create_server("S1", LEFT * 3)
        s2 = self.create_server("S2", ORIGIN)
        s3 = self.create_server("S3", RIGHT * 3)

        servers = VGroup(s1, s2, s3)

        # Role labels
        label1 = Text("Follower", font_size=24, color=FOLLOWER_COLOR).next_to(s1, DOWN)
        label2 = Text("Follower", font_size=24, color=FOLLOWER_COLOR).next_to(s2, DOWN)
        label3 = Text("Follower", font_size=24, color=FOLLOWER_COLOR).next_to(s3, DOWN)
        labels = VGroup(label1, label2, label3)

        # Term counter
        term_text = Text("term: 0", font_size=32, color=WHITE).to_edge(UP)

        # Shot 3.1 [6s]: Three servers as Followers
        self.play(FadeIn(servers), run_time=1)
        self.play(Write(labels), run_time=1)
        self.play(Write(term_text), run_time=1)
        self.wait(3)

        # Shot 3.2 [7s]: S1 becomes Leader
        new_label1 = Text("Leader", font_size=24, color=LEADER_COLOR).next_to(s1, DOWN)
        crown = (
            Text("👑", font_size=28).next_to(s1, UP, buff=0.2)
        )  # Using emoji for crown

        self.play(
            s1[0].animate.set_color(LEADER_COLOR),
            Transform(label1, new_label1),
            run_time=1,
        )
        self.play(GrowFromCenter(crown), run_time=1)
        self.wait(4)

        # Shot 3.3 [6s]: Term increments
        new_term = Text("term: 1", font_size=32, color=WHITE).to_edge(UP)
        self.play(Transform(term_text, new_term), run_time=1)
        self.play(Indicate(term_text, color=LEADER_COLOR), run_time=1)
        self.wait(3)

        # Shot 3.4 [6s]: One leader per term guarantee
        guarantee = Text(
            "One leader per term — guaranteed", font_size=28, color=LEADER_COLOR
        ).to_edge(DOWN)
        self.play(Write(guarantee), run_time=2)
        self.wait(3)

    def create_server(self, label, position):
        circle = Circle(radius=0.6, color=FOLLOWER_COLOR, fill_opacity=0.3)
        text = Text(label, font_size=28, color=WHITE)
        server = VGroup(circle, text).move_to(position)
        return server
