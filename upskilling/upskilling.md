### 1. Git branch

Get your local `main` branch up to date with upstream's `main` branch:

```sh
git fetch upstream
git checkout main
git rebase upstream/main
```

Create a local branch from `main` for your development:

```sh
# While on the main branch
git checkout -b <branch name>
# ex: git checkout -b feature
```

Keep your branch up to date during development:

```sh
git fetch upstream
git rebase upstream/main

# or: git pull --rebase upstream main
```

### 4. Commit

Make code changes on the `feature` branch and commit them with your signature

```sh
git commit -s
```

Follow the [commit style guidelines](#commit-style-guideline).

Make sure to squash your commits before opening a pull request. This is preferred so that your pull request can be merged as is without requesting to be squashed before merge if possible.

### 5. Push

Push your branch to your remote fork:

```sh
git push -f <remote name> <branch name>
```

### 6. Open a pull request

1. Visit your fork at `https://github.com/$GITHUB_USERNAME/osm`.
1. Open a pull request from your `feature` branch using the `Compare & Pull Request` button.
1. Fill the pull request template and provide enough description so that it can be reviewed.

If your pull request is not ready to be reviewed, open it as a draft.


Check the log:
`git log --graph --decorate --pretty=oneline --abbrev-commit`

And follow the steps in this blog: https://www.scraggo.com/how-to-squash-commits/ 

`git rebase -i HEAD~5`
5 being the number of commits to squash



```bash
az account set -s "CSE Dev Crews Americas West"

```

