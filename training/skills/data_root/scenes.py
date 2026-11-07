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
        Part("title", ["Murmurent keeps memory in three tiers. The third is the data root: the lab's big files, on the "
                       "lab's server, in folders with rules. This is what those folders are and how a project uses them."]),
        Part("cards", chapter="Three tiers", heading="Tier three: bulk data on the filesystem", source="rules/data-storage.md",
             colour=TEAL,
             quotes=[Quote("All data except very small files in-repo lives under $MURMURENT_DATA_ROOT", "lives under"),
                     Quote("The data root is a per-machine resource, not a synced one", "per-machine"),
                     Quote("Tier-3 (protected, and very large genomic) data is server-resident.", "server-resident")],
             narration=["Tier one is what an agent sees in one session; tier two is what the oracle remembers; tier "
                        "three is bulk data: reads, images, big analyses. It all lives under the data root, a "
                        "per-machine resource, not a synced one. Protected or very large data is server-resident, "
                        "reached over the network, never copied to a laptop."]),
        Part("terminal", chapter="The folders", heading="One data root, one folder per purpose", transcript=T_TREE,
             title="Terminal, on the lab server", colour=TEAL,
             notes=[("Eight folders at the top, nothing else. Each has subfolders named after projects.", "nothing else"),
                    ("A repository called project_x has immutable/project_x and append_only/project_x.", "project x has"),
                    ("append_only mirrors the repository's exp folder: exp/3_qc writes to append_only/project_x/3_qc.", "mirrors")],
             narration=["The top of the data root holds eight folders and nothing else; each has one subfolder per "
                        "project, with the project's own name. A repository called project x has immutable slash project "
                        "x for its original data and append only slash project x for its outputs.",
                        "Append only mirrors the repository's exp folder: exp slash three q c writes to append only slash "
                        "project x slash three q c. Code and data share a name."]),
        Part("cards", chapter="What each folder is for", heading="What each folder is for", source="docs/lab_folders.md",
             colour=AMBER,
             quotes=[Quote("Original data from the lab, a collaborator or a public source. Read-only once placed.", "immutable"),
                     Quote("New files and new versions are added; nothing is overwritten or deleted.", "append only"),
                     Quote("A project's working data that may change.", "modifiable"),
                     Quote("Files waiting to go to long-term storage, after which they are removed from the server. People move files here; no agent changes them.", "mothballed"),
                     Quote("Each person's large files, such as conda environments, since home folders are small.", "cottage")],
             narration=["Immutable: original data, read-only once placed. Append only: analyses, where new files and "
                        "new versions are added and nothing is overwritten or deleted. Modifiable: working data that "
                        "may change.",
                        "Mothballed: files waiting for long-term storage; people move them there and no agent touches "
                        "them. Release: the lab's copy of published work. Cottage: each person's large files, such as "
                        "conda environments, named by login. Tools and db are shared."]),
        Part("terminal", chapter="What the hooks refuse", heading="What the hooks refuse, in their own words", transcript=T_HOOKS,
             title="Inside a Claude Code session", colour=RED,
             notes=[("A write into immutable: refused.", "immutable"),
                    ("Overwriting under append only: refused; version the name instead.", "version"),
                    ("A delete under the data root: refused.", "delete"),
                    ("Guardrails for agents, not a security perimeter: a plain shell does not go through them.", "perimeter")],
             narration=["Inside Claude Code, hooks uphold two folders. A write into immutable is refused. Overwriting "
                        "under append only is refused, with the advice to version the name. A delete under the data "
                        "root is refused. These are the hooks' real messages.",
                        "They are guardrails for agents, not a security perimeter: a plain shell does not go through them."]),
        Part("terminal", chapter="Keeping it tidy", heading="The layout check: report, never tidy", transcript=T_LAYOUT,
             title="Terminal: a demo data root with three mistakes", colour=AMBER,
             notes=[("A folder being phased out, a loose file, a subfolder named after no project.", "three"),
                    ("The PI decides. Agents report; they never move, rename or delete.", "decides")],
             narration=["One command checks the data root against the protocol. Here it ran on a demo data root with "
                        "three mistakes planted: a folder being phased out, a loose file, a subfolder named after no "
                        "project. It reads names only; the PI decides; agents report and never tidy."]),
        Part("howto", heading="How to use it",
             prompt="ask the blacksmith to run exp/3_qc and write the results under append_only/project_x/3_qc, versioned",
             cards=[("Name the folder", "Original data to immutable, outputs to append_only under the experiment's name, working files to modifiable."),
                    ("Version, never overwrite", "A new result is file_2.csv beside file_1.csv; list the old one in src/ready_to_delete.md."),
                    ("Big and protected stays put", "Reach the server over SSH or a mount; never copy protected data to a laptop.")],
             docs=["rules/data-storage.md", "docs/lab_folders.md", "rules/project-structure.md"],
             narration=["Name the folder when you ask an agent for work: original data to immutable, outputs to append "
                        "only under the experiment's name, working files to modifiable. Version, never overwrite. Big "
                        "or protected data stays on the server, reached, not copied."]),
    ],
)
