# Scene 4: Leader Election
# Duration: 45 seconds

from manim import *

# Color palette
LEADER_COLOR = "#3498db"
FOLLOWER_COLOR = "#95a5a6"
CANDIDATE_COLOR = "#f1c40f"
BG_COLOR = "#1a1a2e"


class ElectionScene(Scene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # Create three server nodes in triangle
        s1 = self.create_server("S1", UP * 1.5)
        s2 = self.create_server("S2", DOWN * 1 + LEFT * 2.5)
        s3 = self.create_server("S3", DOWN * 1 + RIGHT * 2.5)

        servers = VGroup(s1, s2, s3)

        # Role labels
        label1 = Text("Follower", font_size=20, color=FOLLOWER_COLOR).next_to(
            s1, DOWN, buff=0.15
        )
        label2 = Text("Follower", font_size=20, color=FOLLOWER_COLOR).next_to(
            s2, DOWN, buff=0.15
        )
        label3 = Text("Follower", font_size=20, color=FOLLOWER_COLOR).next_to(
            s3, DOWN, buff=0.15
        )
        labels = VGroup(label1, label2, label3)

        # Term counter
        term_text = Text("term: 0", font_size=28, color=WHITE).to_corner(UL)

        # Initial setup
        self.play(FadeIn(servers), FadeIn(labels), FadeIn(term_text), run_time=1)

        # Shot 4.1 [6s]: Clock appears next to S1
        clock = (
            Circle(radius=0.3, color=WHITE, stroke_width=2)
            .next_to(s1, RIGHT, buff=0.3)
            .shift(UP * 0.3)
        )
        clock_hand = Line(
            clock.get_center(), clock.get_center() + UP * 0.25, color=WHITE
        )
        clock_group = VGroup(clock, clock_hand)

        self.play(Create(clock_group), run_time=1)
        self.play(Rotate(clock_hand, angle=-PI, about_point=clock.get_center()), run_time=2)
        self.wait(2)

        # Shot 4.2 [6s]: Timeout triggers
        timeout_flash = Flash(clock.get_center(), color=CANDIDATE_COLOR, line_length=0.2)
        self.play(timeout_flash, run_time=0.5)
        self.play(s1[0].animate.set_color(CANDIDATE_COLOR), run_time=0.5)
        self.wait(4)

        # Shot 4.3 [6s]: S1 becomes Candidate, term increments
        new_label1 = Text("Candidate", font_size=20, color=CANDIDATE_COLOR).next_to(
            s1, DOWN, buff=0.15
        )
        new_term = Text("term: 1", font_size=28, color=WHITE).to_corner(UL)

        self.play(
            Transform(label1, new_label1), Transform(term_text, new_term), run_time=1
        )
        self.play(Indicate(term_text), run_time=1)
        self.wait(4)

        # Shot 4.4 [8s]: RequestVote arrows
        vote_req_label = Text("RequestVote", font_size=16, color=CANDIDATE_COLOR)

        arrow_to_s2 = Arrow(
            s1.get_center(), s2.get_center(), buff=0.7, color=CANDIDATE_COLOR
        )
        arrow_to_s3 = Arrow(
            s1.get_center(), s3.get_center(), buff=0.7, color=CANDIDATE_COLOR
        )

        label_s2 = vote_req_label.copy().next_to(arrow_to_s2, LEFT, buff=0.1)
        label_s3 = vote_req_label.copy().next_to(arrow_to_s3, RIGHT, buff=0.1)

        self.play(
            Create(arrow_to_s2),
            Create(arrow_to_s3),
            FadeIn(label_s2),
            FadeIn(label_s3),
            run_time=2,
        )
        self.wait(6)

        # Shot 4.5 [7s]: Votes return
        vote_yes_label = Text("Vote ✓", font_size=16, color=LEADER_COLOR)

        return_arrow_s2 = Arrow(
            s2.get_center(), s1.get_center(), buff=0.7, color=LEADER_COLOR
        )
        return_arrow_s3 = Arrow(
            s3.get_center(), s1.get_center(), buff=0.7, color=LEADER_COLOR
        )

        return_label_s2 = vote_yes_label.copy().next_to(return_arrow_s2, RIGHT, buff=0.1)
        return_label_s3 = vote_yes_label.copy().next_to(return_arrow_s3, LEFT, buff=0.1)

        vote_counter = Text("Votes: 2/3", font_size=24, color=LEADER_COLOR).to_corner(
            UR
        )

        self.play(
            FadeOut(arrow_to_s2),
            FadeOut(arrow_to_s3),
            FadeOut(label_s2),
            FadeOut(label_s3),
            run_time=0.5,
        )
        self.play(
            Create(return_arrow_s2),
            Create(return_arrow_s3),
            FadeIn(return_label_s2),
            FadeIn(return_label_s3),
            run_time=1,
        )
        self.play(FadeIn(vote_counter), run_time=1)
        self.wait(4.5)

        # Shot 4.6 [6s]: S1 becomes Leader
        self.play(
            FadeOut(return_arrow_s2),
            FadeOut(return_arrow_s3),
            FadeOut(return_label_s2),
            FadeOut(return_label_s3),
            FadeOut(clock_group),
            run_time=0.5,
        )

        new_label1_leader = Text("Leader", font_size=20, color=LEADER_COLOR).next_to(
            s1, DOWN, buff=0.15
        )
        crown = Text("👑", font_size=24).next_to(s1, UP, buff=0.1)

        self.play(
            s1[0].animate.set_color(LEADER_COLOR),
            Transform(label1, new_label1_leader),
            run_time=1,
        )
        self.play(GrowFromCenter(crown), run_time=1)
        self.wait(4)

        # Shot 4.7 [6s]: Higher term rule
        rule_box = VGroup(
            Rectangle(width=6, height=0.8, color=LEADER_COLOR, fill_opacity=0.2),
            Text(
                "Higher term always wins", font_size=24, color=WHITE
            ),
        ).to_edge(DOWN)
        rule_box[1].move_to(rule_box[0])

        self.play(FadeIn(rule_box), run_time=1)
        self.wait(5)

    def create_server(self, label, position):
        circle = Circle(radius=0.5, color=FOLLOWER_COLOR, fill_opacity=0.3)
        text = Text(label, font_size=24, color=WHITE)
        server = VGroup(circle, text).move_to(position)
        return server
