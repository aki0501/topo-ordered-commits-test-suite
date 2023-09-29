#!/usr/bin/env python3

# Keep the function signature,
# but replace its body with your implementation.
#
# Note that this is the driver function.
# Please write a well-structured implemention by creating other functions
# outside of this one, each of which has a designated purpose.
#
# As a good programming practice,
# please do not use any script-level variables that are modifiable.
# This is because those variables live on forever once the script is imported,
# and the changes to them will persist across different invocations of the
# imported functions.

# I used strace to verify that I am not using other commands by running
# 'strace -f -o topo-test.tr pytest'
# which checks for the system calls made by running pytest, and sends its
# output to a new file called 'topo-test.tr'.

import sys
import os
import zlib
import copy

def topo_order_commits():
    git_dirpath = find_git_directory()
    local_branches_dict = get_local_branches(git_dirpath)
    commit_graph = make_commit_graph(local_branches_dict)
    ordered_graph = topo_sort(commit_graph)
    print_topo_sort(commit_graph, ordered_graph, local_branches_dict)

class CommitNode:
    def __init__(self, commit_hash):
        """
        :type commit_hash: str
        """
        self.commit_hash = commit_hash
        self.parents = set()
        self.children = set()

def get_local_branches(git_dirpath):
    # Get path to refs/heads/
    path_to_branches = os.path.join(git_dirpath, 'refs', 'heads')
    branches = {}

    # For each dir in refs/heads/, add files to dict
    for dirpath, _, filenames in os.walk(path_to_branches):
        if not filenames:
            continue
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)

            # Make sure file exists
            if not os.path.exists(file_path):
                exit(1)

            file = open(file_path, "r")
            hash = file.read().strip()

            # Grab the branch names from the path
            branch_name = file_path[len(os.getcwd() + "/.git/refs/heads/"):]

            if hash not in branches:
                branches[hash] = set()
            branches[hash].add(branch_name)

    return branches

def find_git_directory():
    git_dirpath = ""
    parent_dirname = os.getcwd()

    while parent_dirname != '/':
        # Check if <parent_dirname>/.git exists
        git_path_attempt = os.path.join(parent_dirname, '.git')

        # If .git exists here, don't continue traversing upward
        if os.path.exists(git_path_attempt):
            git_dirpath = git_path_attempt
            break

        # If not, move up the directory tree
        parent_dirname = os.path.dirname(parent_dirname)

    # If .git folder doesn't exist, fail
    if git_dirpath == "":
        print("Not inside a Git repository", file=sys.stderr)
        exit(1)

    return git_dirpath

def parents(hash):
    results = set()

    # Separate commit hash into directory and file
    directory = hash[:2]
    file = hash[2:]
    cwd = os.getcwd()

    # Get path to file
    path_to_hash_file = "{0}/.git/objects/{1}/{2}".format(cwd, directory, file)

    file_exists = os.path.isfile(path_to_hash_file)

    # This shouldn't happen normally!
    if not file_exists:
        sys.stderr.write("Object for hash {0} not found".format(hash))
        sys.exit(1)

    object = open(path_to_hash_file, "rb").read()
    decompressed_object = zlib.decompress(object).decode("utf-8")

    # Split by spaces and new lines
    decompressed_object = decompressed_object.replace("\n", " ").split(" ")

    for i, text in enumerate(decompressed_object):
        next_in_bounds = i + 1 < len(decompressed_object) - 1
        if text == 'parent' and next_in_bounds:
            results.add(decompressed_object[i + 1])
    return results

def make_commit_graph(branch_dict):
    # Get a unique list of hashes from the dictionary
    stack = set(branch_dict.keys())
    # Final commit graph represented as hash to CommitNode
    result = dict()
    visited = set()

    while stack:
        curr_hash = stack.pop().strip()

        if curr_hash in visited:
            continue
        else:
            visited.add(curr_hash)

        node_created = curr_hash in result

        if not node_created:
            result[curr_hash] = CommitNode(curr_hash)

        # Get the current CommitNode and the hashes for its parents
        curr_node = result[curr_hash]
        curr_parents = parents(curr_hash)

        for parent in curr_parents:
            parent_created = parent in result
            if not parent_created:
                result[parent] = CommitNode(curr_hash)

            curr_parent = result[parent]

            curr_node.parents.add(parent)
            curr_parent.children.add(curr_hash)

            if parent not in visited:
                stack.add(parent)
    return result

def topo_sort(graph):
    # Apply Kahn's algorithm to get the topological sort
    result = []
    # Queue of commits to process
    queue = []
    copied_graph = copy.deepcopy(graph)

    # Initialize the queue with childless nodes
    for hash in copied_graph:
        has_no_children = len(copied_graph[hash].children) == 0
        if has_no_children:
            queue.append(hash)

    while queue:
        curr_hash = queue.pop(0)
        result.append(curr_hash)

        curr_parents = list(copied_graph[curr_hash].parents)

        for phash in curr_parents:
            copied_graph[curr_hash].parents.remove(phash)
            copied_graph[phash].children.remove(curr_hash)

            childless_parent = len(copied_graph[phash].children) == 0
            if childless_parent:
                queue.append(phash)

    # Check for cycles
    has_cycle = len(result) != len(graph)

    # This should never happen, there should not be any cycles in git graph
    if has_cycle:
        sys.stderr.write("Cycle detected in graph")
        sys.exit(1)

    return result

def print_topo_sort(commit_graph, ordered_graph, local_branches_dict):
    discontinuity = False
    num_commits = len(ordered_graph)
    for i in range(num_commits):
        curr_hash = ordered_graph[i]
        # If there was a sticky end in the past,
        # then there needs to be a sticky start
        if discontinuity:
            discontinuity = False
            sticky_start = ' '.join(commit_graph[curr_hash].children)
            print("={0}".format(sticky_start))

        # Print the current hash with local branches if they exist
        if curr_hash in local_branches_dict:
            branch_names = " ".join(sorted(local_branches_dict[curr_hash]))
            print("{0} {1}".format(curr_hash, branch_names))
        else:
            print(curr_hash)

        # Handle any sticky end by checking next commit in topo ordering
        not_last_commit = i + 1 < num_commits
        if not_last_commit \
            and ordered_graph[i + 1] not in commit_graph[curr_hash].parents:
            discontinuity = True
            sticky_end = ' '.join(commit_graph[curr_hash].parents)
            print("{0}=\n".format(sticky_end))

if __name__ == '__main__':
    topo_order_commits()
