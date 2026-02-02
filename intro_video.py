"""
Raft Consensus Algorithm - Introduction Video

This video provides an animated introduction to:
  - What distributed consensus is
  - The problem Raft solves
  - Leader election process
  - Log replication mechanism
  - Safety guarantees
  - This implementation's architecture

Installation (requires system dependencies):
    # Ubuntu/Debian
    sudo apt install libpango1.0-dev libcairo2-dev ffmpeg
    pip install manim

    # macOS
    brew install pango cairo ffmpeg
    pip install manim

Rendering:
    Low quality (fast preview):   manim -pql intro_video.py RaftIntro
    Medium quality:               manim -pqm intro_video.py RaftIntro
    High quality (production):    manim -pqh intro_video.py RaftIntro

Output will be saved to: media/videos/intro_video/
"""

from manim import *


class RaftIntro(Scene):
    def construct(self):
        # Color scheme
        LEADER_COLOR = GREEN
        FOLLOWER_COLOR = RED
        CANDIDATE_COLOR = YELLOW
        MESSAGE_COLOR = BLUE

        # ===== TITLE SECTION =====
        title = Text("The Raft Consensus Algorithm", font_size=48)
        subtitle = Text("Distributed Systems Made Simple", font_size=28, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.5)

        self.play(Write(title), run_time=1.5)
        self.play(FadeIn(subtitle, shift=UP), run_time=1)
        self.wait(1)
        self.play(FadeOut(title), FadeOut(subtitle))

        # ===== THE PROBLEM =====
        problem_title = Text("The Problem", font_size=40, color=YELLOW)
        problem_title.to_edge(UP, buff=0.5)
        self.play(Write(problem_title))

        # Show multiple servers
        servers = VGroup()
        server_labels = ["Server 1", "Server 2", "Server 3"]
        for i, label in enumerate(server_labels):
            server = VGroup(
                RoundedRectangle(width=2, height=1.5, corner_radius=0.2, color=WHITE),
                Text(label, font_size=20)
            )
            server[1].move_to(server[0].get_center())
            servers.add(server)

        servers.arrange(RIGHT, buff=1.5)
        servers.shift(DOWN * 0.5)

        self.play(LaggedStart(*[FadeIn(s, scale=0.8) for s in servers], lag_ratio=0.2))
        self.wait(0.5)

        # Question mark above servers
        question = Text("How do they agree?", font_size=32, color=BLUE)
        question.next_to(servers, UP, buff=0.8)
        self.play(Write(question))
        self.wait(1)

        # Show conflicting data
        data_boxes = VGroup()
        data_values = ["x = 5", "x = 7", "x = 5"]
        for i, (server, value) in enumerate(zip(servers, data_values)):
            box = VGroup(
                Rectangle(width=1.2, height=0.6, color=RED if value == "x = 7" else GREEN),
                Text(value, font_size=18)
            )
            box[1].move_to(box[0].get_center())
            box.next_to(server, DOWN, buff=0.3)
            data_boxes.add(box)

        self.play(LaggedStart(*[FadeIn(b, shift=UP) for b in data_boxes], lag_ratio=0.15))
        self.wait(0.5)

        inconsistent = Text("Inconsistent!", font_size=28, color=RED)
        inconsistent.next_to(data_boxes, DOWN, buff=0.5)
        self.play(Write(inconsistent))
        self.wait(1)

        self.play(
            FadeOut(problem_title), FadeOut(servers), FadeOut(question),
            FadeOut(data_boxes), FadeOut(inconsistent)
        )

        # ===== THE SOLUTION: RAFT =====
        solution_title = Text("The Solution: Raft", font_size=40, color=GREEN)
        solution_title.to_edge(UP, buff=0.5)
        self.play(Write(solution_title))

        # Key concepts
        concepts = VGroup(
            Text("1. Leader Election", font_size=28),
            Text("2. Log Replication", font_size=28),
            Text("3. Safety & Consistency", font_size=28),
        )
        concepts.arrange(DOWN, aligned_edge=LEFT, buff=0.5)
        concepts.center()

        for concept in concepts:
            self.play(Write(concept), run_time=0.7)
            self.wait(0.3)

        self.wait(1)
        self.play(FadeOut(solution_title), FadeOut(concepts))

        # ===== LEADER ELECTION =====
        election_title = Text("1. Leader Election", font_size=36, color=YELLOW)
        election_title.to_edge(UP, buff=0.5)
        self.play(Write(election_title))

        # Create 3 server circles
        def create_server(label, color=FOLLOWER_COLOR):
            circle = Circle(radius=0.6, color=color, fill_opacity=0.3)
            text = Text(label, font_size=20)
            text.move_to(circle.get_center())
            return VGroup(circle, text)

        s1 = create_server("S1")
        s2 = create_server("S2")
        s3 = create_server("S3")

        cluster = VGroup(s1, s2, s3)
        s1.move_to(UP * 0.5)
        s2.move_to(DOWN * 1.2 + LEFT * 1.5)
        s3.move_to(DOWN * 1.2 + RIGHT * 1.5)

        role_labels = VGroup(
            Text("Follower", font_size=16, color=FOLLOWER_COLOR),
            Text("Follower", font_size=16, color=FOLLOWER_COLOR),
            Text("Follower", font_size=16, color=FOLLOWER_COLOR),
        )
        for label, server in zip(role_labels, cluster):
            label.next_to(server, DOWN, buff=0.2)

        self.play(
            LaggedStart(*[FadeIn(s) for s in cluster], lag_ratio=0.2),
            LaggedStart(*[FadeIn(l) for l in role_labels], lag_ratio=0.2)
        )
        self.wait(0.5)

        # Timeout - S1 becomes candidate
        timeout_text = Text("Timeout!", font_size=24, color=YELLOW)
        timeout_text.next_to(s1, RIGHT, buff=0.3)
        self.play(FadeIn(timeout_text, scale=1.5))

        new_role = Text("Candidate", font_size=16, color=CANDIDATE_COLOR)
        new_role.next_to(s1, DOWN, buff=0.2)
        self.play(
            s1[0].animate.set_color(CANDIDATE_COLOR),
            Transform(role_labels[0], new_role),
            FadeOut(timeout_text)
        )

        # Request votes
        vote_req1 = Arrow(s1.get_center(), s2.get_center(), buff=0.7, color=MESSAGE_COLOR)
        vote_req2 = Arrow(s1.get_center(), s3.get_center(), buff=0.7, color=MESSAGE_COLOR)
        vote_text = Text("RequestVote", font_size=14, color=MESSAGE_COLOR)
        vote_text.next_to(vote_req1, LEFT, buff=0.1)

        self.play(
            GrowArrow(vote_req1), GrowArrow(vote_req2),
            FadeIn(vote_text)
        )
        self.wait(0.5)

        # Receive votes
        vote_resp1 = Arrow(s2.get_center(), s1.get_center(), buff=0.7, color=GREEN)
        vote_resp2 = Arrow(s3.get_center(), s1.get_center(), buff=0.7, color=GREEN)

        self.play(
            FadeOut(vote_req1), FadeOut(vote_req2), FadeOut(vote_text),
            GrowArrow(vote_resp1), GrowArrow(vote_resp2)
        )

        # Become leader
        majority = Text("Majority votes!", font_size=20, color=GREEN)
        majority.next_to(s1, UP, buff=0.3)
        self.play(FadeIn(majority))
        self.wait(0.3)

        leader_role = Text("Leader", font_size=16, color=LEADER_COLOR)
        leader_role.next_to(s1, DOWN, buff=0.2)
        self.play(
            s1[0].animate.set_color(LEADER_COLOR).set_fill(LEADER_COLOR, opacity=0.4),
            Transform(role_labels[0], leader_role),
            FadeOut(vote_resp1), FadeOut(vote_resp2), FadeOut(majority)
        )

        self.wait(1)
        self.play(
            FadeOut(election_title), FadeOut(cluster), FadeOut(role_labels)
        )

        # ===== LOG REPLICATION =====
        log_title = Text("2. Log Replication", font_size=36, color=YELLOW)
        log_title.to_edge(UP, buff=0.5)
        self.play(Write(log_title))

        # Create servers with logs
        def create_server_with_log(name, color, entries):
            server = Circle(radius=0.5, color=color, fill_opacity=0.3)
            label = Text(name, font_size=18)
            label.move_to(server.get_center())

            log = VGroup()
            for i, entry in enumerate(entries):
                box = Rectangle(width=0.6, height=0.4, color=WHITE, fill_opacity=0.2)
                text = Text(entry, font_size=12)
                text.move_to(box.get_center())
                entry_group = VGroup(box, text)
                log.add(entry_group)
            log.arrange(RIGHT, buff=0.05)
            log.next_to(server, DOWN, buff=0.3)

            return VGroup(server, label, log)

        leader = create_server_with_log("Leader", LEADER_COLOR, ["a", "b"])
        f1 = create_server_with_log("F1", FOLLOWER_COLOR, ["a", "b"])
        f2 = create_server_with_log("F2", FOLLOWER_COLOR, ["a", "b"])

        leader.move_to(UP * 1 + LEFT * 3)
        f1.move_to(UP * 1 + RIGHT * 0.5)
        f2.move_to(UP * 1 + RIGHT * 3.5)

        self.play(FadeIn(leader), FadeIn(f1), FadeIn(f2))
        self.wait(0.5)

        # Client sends command
        client = VGroup(
            Rectangle(width=1.2, height=0.6, color=BLUE),
            Text("Client", font_size=16)
        )
        client[1].move_to(client[0].get_center())
        client.move_to(DOWN * 1.5 + LEFT * 3)

        self.play(FadeIn(client))

        cmd_arrow = Arrow(client.get_top(), leader[0].get_bottom(), buff=0.2, color=BLUE)
        cmd_text = Text("append 'c'", font_size=14, color=BLUE)
        cmd_text.next_to(cmd_arrow, LEFT, buff=0.1)

        self.play(GrowArrow(cmd_arrow), FadeIn(cmd_text))
        self.wait(0.3)

        # Leader appends to its log
        new_entry = VGroup(
            Rectangle(width=0.6, height=0.4, color=YELLOW, fill_opacity=0.5),
            Text("c", font_size=12)
        )
        new_entry[1].move_to(new_entry[0].get_center())
        new_entry.next_to(leader[2], RIGHT, buff=0.05)

        self.play(FadeIn(new_entry, scale=1.5))
        leader[2].add(new_entry)
        self.play(FadeOut(cmd_arrow), FadeOut(cmd_text))

        # Replicate to followers
        rep_arrow1 = Arrow(leader[0].get_right(), f1[0].get_left(), buff=0.2, color=MESSAGE_COLOR)
        rep_arrow2 = Arrow(f1[0].get_right(), f2[0].get_left(), buff=0.2, color=MESSAGE_COLOR)

        append_text = Text("AppendEntries", font_size=14, color=MESSAGE_COLOR)
        append_text.next_to(rep_arrow1, UP, buff=0.1)

        self.play(GrowArrow(rep_arrow1), FadeIn(append_text))

        # F1 appends
        f1_new = VGroup(
            Rectangle(width=0.6, height=0.4, color=YELLOW, fill_opacity=0.5),
            Text("c", font_size=12)
        )
        f1_new[1].move_to(f1_new[0].get_center())
        f1_new.next_to(f1[2], RIGHT, buff=0.05)
        self.play(FadeIn(f1_new, scale=1.5))

        self.play(
            FadeOut(rep_arrow1), FadeOut(append_text),
            GrowArrow(rep_arrow2)
        )

        # F2 appends
        f2_new = VGroup(
            Rectangle(width=0.6, height=0.4, color=YELLOW, fill_opacity=0.5),
            Text("c", font_size=12)
        )
        f2_new[1].move_to(f2_new[0].get_center())
        f2_new.next_to(f2[2], RIGHT, buff=0.05)
        self.play(FadeIn(f2_new, scale=1.5), FadeOut(rep_arrow2))

        # Committed!
        committed = Text("Committed!", font_size=24, color=GREEN)
        committed.move_to(DOWN * 0.5)
        self.play(
            Write(committed),
            new_entry[0].animate.set_color(GREEN),
            f1_new[0].animate.set_color(GREEN),
            f2_new[0].animate.set_color(GREEN),
        )

        self.wait(1)
        self.play(
            FadeOut(log_title), FadeOut(leader), FadeOut(f1), FadeOut(f2),
            FadeOut(client), FadeOut(committed),
            FadeOut(f1_new), FadeOut(f2_new)
        )

        # ===== KEY GUARANTEES =====
        guarantee_title = Text("3. Safety Guarantees", font_size=36, color=YELLOW)
        guarantee_title.to_edge(UP, buff=0.5)
        self.play(Write(guarantee_title))

        guarantees = VGroup(
            VGroup(
                Text("Election Safety", font_size=24, color=GREEN),
                Text("Only one leader per term", font_size=18, color=GRAY),
            ),
            VGroup(
                Text("Log Matching", font_size=24, color=GREEN),
                Text("Same index + term = same entries", font_size=18, color=GRAY),
            ),
            VGroup(
                Text("Leader Completeness", font_size=24, color=GREEN),
                Text("Committed entries survive leader changes", font_size=18, color=GRAY),
            ),
        )

        for g in guarantees:
            g.arrange(DOWN, buff=0.1, aligned_edge=LEFT)

        guarantees.arrange(DOWN, buff=0.6, aligned_edge=LEFT)
        guarantees.center().shift(DOWN * 0.3)

        for g in guarantees:
            self.play(FadeIn(g, shift=RIGHT), run_time=0.8)
            self.wait(0.5)

        self.wait(1)
        self.play(FadeOut(guarantee_title), FadeOut(guarantees))

        # ===== THIS IMPLEMENTATION =====
        impl_title = Text("This Implementation", font_size=36, color=BLUE)
        impl_title.to_edge(UP, buff=0.5)
        self.play(Write(impl_title))

        # Show architecture
        components = VGroup(
            VGroup(
                RoundedRectangle(width=2.5, height=1, corner_radius=0.1, color=GREEN),
                Text("RaftServer", font_size=18),
                Text("Main orchestrator", font_size=12, color=GRAY),
            ),
            VGroup(
                RoundedRectangle(width=2.5, height=1, corner_radius=0.1, color=BLUE),
                Text("RaftState", font_size=18),
                Text("Core algorithm", font_size=12, color=GRAY),
            ),
            VGroup(
                RoundedRectangle(width=2.5, height=1, corner_radius=0.1, color=YELLOW),
                Text("RaftNode", font_size=18),
                Text("Network layer", font_size=12, color=GRAY),
            ),
            VGroup(
                RoundedRectangle(width=2.5, height=1, corner_radius=0.1, color=RED),
                Text("RaftRole", font_size=18),
                Text("Role transitions", font_size=12, color=GRAY),
            ),
        )

        for comp in components:
            comp[1].move_to(comp[0].get_center() + UP * 0.15)
            comp[2].move_to(comp[0].get_center() + DOWN * 0.2)

        components.arrange_in_grid(rows=2, cols=2, buff=0.5)
        components.center().shift(DOWN * 0.3)

        self.play(
            LaggedStart(*[FadeIn(c, scale=0.8) for c in components], lag_ratio=0.2)
        )

        # Features
        features = VGroup(
            Text("Pure Python", font_size=20),
            Text("No dependencies", font_size=20),
            Text("Educational focus", font_size=20),
        )
        features.arrange(RIGHT, buff=1)
        features.to_edge(DOWN, buff=0.8)

        self.play(FadeIn(features, shift=UP))
        self.wait(2)

        self.play(FadeOut(impl_title), FadeOut(components), FadeOut(features))

        # ===== FINAL =====
        final_title = Text("Raft", font_size=72, color=WHITE)
        final_subtitle = Text(
            "Understandable Distributed Consensus",
            font_size=28,
            color=GRAY
        )
        final_subtitle.next_to(final_title, DOWN, buff=0.5)

        self.play(Write(final_title), run_time=1)
        self.play(FadeIn(final_subtitle, shift=UP))

        # Credit
        credit = Text(
            "Based on David Beazley's Rafting Trip course",
            font_size=18,
            color=GRAY_B
        )
        credit.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(credit))

        self.wait(2)
        self.play(FadeOut(final_title), FadeOut(final_subtitle), FadeOut(credit))
