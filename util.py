import subprocess


def dict_tree_walk(node, field):
    result = {}

    for key, child in node.items():
        if type(child) is dict:
            if field in child:
                result[key] = child
            else:
                result.update(dict_tree_walk(child, field))

    return result


# From http://stackoverflow.com/questions/12826723/possible-to-extract-the-git-repo-revision-hash-via-python-code
def get_git_hash():
    git_process = subprocess.Popen(['git', 'rev-parse', 'HEAD'], stdout=subprocess.PIPE, stderr=None)
    (git_out, _) = git_process.communicate()
    return git_out.strip()
