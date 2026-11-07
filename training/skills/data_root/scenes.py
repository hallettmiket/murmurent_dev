"""The data root (tier-3 memory): the lab folder protocol, what each folder is for, how a project's folders
mirror its repository, and what the hooks refuse. Every terminal scene is a real run on a demo data root."""
from lib.draw import AMBER, RED, TEAL
from lib.movie import Movie, Part, Quote

T_TREE = """
$ echo $MURMURENT_DATA_ROOT
/data/lab_vm
$ ls /data/lab_vm
append_only  cottage  db  immutable  modifiable  mothballed  release  tools
$ ls /data/lab_vm/immutable/project_x /data/lab_vm/append_only/project_x
immutable/project_x:
reads_lane1.fastq.gz
append_only/project_x:
3_qc
$ ls ~/repos/project_x/exp
3_qc
"""

T_HOOKS = """
$ # Claude Code asks to write into immutable; the hook answers
immutable data is read-only by lab policy; refusing Write on
/data/lab_vm/immutable/project_x/reads_lane1.fastq.gz
$ # Claude Code asks to overwrite a result under append_only
protected path is write-once by lab policy; refusing Write that would overwrite
/data/lab_vm/append_only/project_x/3_qc/qc_table_1.csv.
Use an integer-versioned name (e.g. file_2.csv) instead.
$ # Claude Code asks to delete under the data root
PreToolUse:Bash hook error: Cannot delete files/folders from /data/lab_vm - protected directory
"""

T_LAYOUT = """
$ murmurent space layout
Lab folder: /data/lab_vm
Being phased out:
  - sandbox/ is being phased out; ask its owners to move what they still need into a project's folders or their cottage.
Loose files:
  - notes_from_2019.txt is a file at the top of the lab folder; files belong inside a project's folder or a person's cottage.
Named after no project:
  - append_only/stuff/ does not match any project's name; rename it to its project, or make a project for it.
(on this laptop, with no project records, every project folder is listed the same way)
"""

MOVIE = Movie(
    key="data_root",
    title="The data root: where big files live",
    tagline="Tier-3 memory: immutable, append_only, modifiable, and the rest of the lab folder",
    glyph="🗄️",
    colour=TEAL,
    summary="Murmurent's third tier of memory: the lab's data root on its server, what immutable, append_only, modifiable, mothballed, release, cottage, tools and db are for, how a project's folders mirror its repository, what the hooks refuse, and the layout check.",
    parts=[
        Part("title", ["The data root is where a lab's big files live, on the lab's server, in folders with rules. "
                       "This is what those folders are for."]),
        Part("cards", chapter="Three tiers", heading="Tier three: the big files, on the server", source="rules/data-storage.md",
             colour=TEAL,
             quotes=[Quote("All data except very small files in-repo lives under $MURMURENT_DATA_ROOT", "live under"),
                     Quote("Tier-3 (protected, and very large genomic) data is server-resident.", "stays there")],
             narration=["Murmurent keeps memory in three tiers: what an agent sees in one session, what the oracle "
                        "remembers, and the big files. Those live under one folder on the server, the data root, "
                        "and protected or very large data stays there, never copied to a laptop."]),
        Part("terminal", chapter="The folders", heading="One data root, one folder per purpose", transcript=T_TREE,
             title="Terminal, on the lab server", colour=TEAL,
             notes=[("Eight folders at the top, nothing else. Each has subfolders named after projects.", "nothing else"),
                    ("A repository called project_x has immutable/project_x and append_only/project_x.", "project x has"),
                    ("append_only mirrors the repository's exp folder: exp/3_qc writes to append_only/project_x/3_qc.", "mirrors")],
             narration=["Eight folders at the top and nothing else; inside each, one subfolder per project with the "
                        "project's own name. So a repository called project x has immutable slash project x for its "
                        "original data and append only slash project x for its outputs, and append only mirrors the "
                        "repository's exp folder: code and data share a name."]),
        Part("folders", chapter="What each folder is for", heading="What each folder is for", colour=AMBER,
             folders=[("immutable", "original data; read-only once placed", "immutable"),
                      ("append_only", "analyses; new files and new versions only, never overwritten", "append only"),
                      ("modifiable", "working data that may change", "modifiable"),
                      ("mothballed", "waiting for backup; removed from the server afterwards", "mothballed"),
                      ("release", "the lab's copy of what it published", "release"),
                      ("cottage", "one person's large files, not a project's", "cottage"),
                      ("tools", "programs the whole lab uses", "tools"),
                      ("db", "databases several people use", "db")],
             narration=["Immutable is the data as it arrived: from the instrument, a collaborator or a public "
                        "source. Once placed, nobody changes it, so every analysis traces back to it.",
                        "Append only is where analyses write. New files and new versions are added, nothing is ever "
                        "overwritten or deleted, so a result you reported last year is still there. Modifiable is "
                        "the one place a project's data may change: working files, scratch.",
                        "Mothballed is how the server makes room. You move files there that you no longer need on "
                        "the server; they are sent to backup, then removed from mothballed. After that they live on "
                        "the backup server only, not on the storage server. Release holds the lab's own copy of what "
                        "it published: the papers and the software.",
                        "Cottage exists because home folders are small: large files that belong to a person, not a "
                        "project, such as conda environments. One per login. Tools are programs the whole lab uses, "
                        "db the databases several people share."]),
        Part("terminal", chapter="What the hooks refuse", heading="What the hooks refuse, in their own words", transcript=T_HOOKS,
             title="Inside a Claude Code session", colour=RED,
             notes=[("Write into immutable: refused.", "immutable"),
                    ("Overwrite under append only: refused.", "overwrite"),
                    ("Delete under the data root: refused.", "delete")],
             narration=["Inside Claude Code, hooks uphold the rules: a write into immutable, an overwrite under append "
                        "only, a delete under the data root, all refused in these words. Guardrails for agents, not a "
                        "security perimeter: a plain shell does not go through them."]),
        Part("terminal", chapter="Keeping it tidy", heading="The layout check: report, never tidy", transcript=T_LAYOUT,
             title="Terminal: a demo data root with three mistakes", colour=AMBER,
             notes=[("A folder being phased out, a loose file, a subfolder named after no project.", "three"),
                    ("The PI decides. Agents report; they never move, rename or delete.", "decides")],
             narration=["One command checks the data root against the protocol; here on a demo with three mistakes "
                        "planted. It reads names only. The PI decides; agents report and never tidy."]),
        Part("howto", heading="How to use it",
             prompt="ask the blacksmith to run exp/3_qc and write the results under append_only/project_x/3_qc, versioned",
             cards=[("Name the folder", "Original data to immutable, outputs to append_only under the experiment's name, working files to modifiable."),
                    ("Version, never overwrite", "A new result is file_2.csv beside file_1.csv; list the old one in src/ready_to_delete.md."),
                    ("Big and protected stays put", "Reach the server over SSH or a mount; never copy protected data to a laptop.")],
             docs=["rules/data-storage.md", "docs/lab_folders.md", "rules/project-structure.md"],
             narration=["Name the folder when you ask an agent for work: original data to immutable, outputs to append "
                        "only, working files to modifiable. Version, never overwrite. Big data stays on the server."]),
    ],
)
