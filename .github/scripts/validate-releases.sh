#!/usr/bin/env bash
set -euo pipefail

# Validates which components have releases on the current commit and expands
# each one into the image builds CI should run. Outputs a JSON array of build
# entries, one per image to push.
#
# A component that ships a `variants.json` is built once per variant — that is
# how a single component directory publishes several base versions (e.g. one
# Node major per image). A component without that file produces exactly one
# build, tagged as it always has been.
#
# Every entry carries its own fully composed `tags` list, so the tag policy
# lives here rather than being split across this script and the workflow.

# Match the workflow's env; defaults keep the script runnable locally.
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_PREFIX="${IMAGE_PREFIX:-idbi/docker}"

git fetch --tags --force

# Build list of components from manifest keys:
COMPONENTS=$(cat .release-please-manifest.json | jq -r 'keys[]')

echo "Components from manifest:" >&2
echo "$COMPONENTS" >&2

# Build JSON array of components to publish
BUILDS=$(jq -n '[]')

for comp in $COMPONENTS; do
  # comp looks like "php-builder"
  # Find latest tag for this component (because include-component-in-tag=true):
  # tag pattern: <component>@vX.Y.Z
  latest_tag=$(git tag --list "${comp}@v*" --sort=-version:refname | head -n 1 || true)

  if [ -z "${latest_tag}" ]; then
    echo "No tag found for ${comp}, skipping." >&2
    continue
  fi

  # Only build if the latest tag points at current commit (means release happened on this push)
  tag_commit=$(git rev-list -n 1 "${latest_tag}")
  head_commit=$(git rev-parse HEAD)

  if [ "${tag_commit}" != "${head_commit}" ]; then
    echo "Latest ${comp} tag (${latest_tag}) is not on HEAD, skipping." >&2
    continue
  fi

  version="${latest_tag#${comp}@v}"   # X.Y.Z
  major="${version%%.*}"            # X
  image="${REGISTRY}/${IMAGE_PREFIX}-${comp}"

  echo "Validating ${comp} => version=${version}, major=${major}" >&2

  if [ -f "${comp}/variants.json" ]; then
    # One build per variant. The variant matching `default` additionally takes
    # the unsuffixed tags (:X.Y.Z, :X, :latest), so `latest` keeps pointing at
    # one designated base version instead of whichever build finished last.
    entries=$(jq -c \
      --arg comp "$comp" --arg image "$image" \
      --arg version "$version" --arg major "$major" '
      (.build_arg // error("\($comp)/variants.json: \"build_arg\" is required")) as $arg
      | (.default // error("\($comp)/variants.json: \"default\" is required")) as $default
      | (.variants // []) as $variants
      | if ($variants | length) == 0 then
          error("\($comp)/variants.json: \"variants\" must not be empty")
        else . end
      | if ($variants | map(select(.value == $default)) | length) != 1 then
          error("\($comp)/variants.json: \"default\" (\($default)) must match exactly one variant")
        else . end
      | $variants
      | map(
          .value as $value
          | (.suffix // error("\($comp)/variants.json: variant \($value) has no \"suffix\"")) as $suffix
          | {
              component: $comp,
              version: $version,
              major: $major,
              variant: $value,
              label: "\($comp) \($suffix)",
              build_args: "\($arg)=\($value)",
              cache_scope: "\($comp)-\($suffix)",
              tags: (
                [
                  "\($image):\($version)-\($suffix)",
                  "\($image):\($major)-\($suffix)",
                  "\($image):\($suffix)"
                ]
                + (if $value == $default then
                     [
                       "\($image):\($version)",
                       "\($image):\($major)",
                       "\($image):latest"
                     ]
                   else [] end)
                | join("\n")
              )
            }
        )
    ' "${comp}/variants.json")

    echo "  ${comp} has variants: $(echo "$entries" | jq -r 'map(.variant) | join(", ")')" >&2
  else
    entries=$(jq -nc \
      --arg comp "$comp" --arg image "$image" \
      --arg version "$version" --arg major "$major" '
      [{
        component: $comp,
        version: $version,
        major: $major,
        variant: "",
        label: $comp,
        build_args: "",
        cache_scope: $comp,
        tags: ([
          "\($image):\($version)",
          "\($image):\($major)",
          "\($image):latest"
        ] | join("\n"))
      }]
    ')
  fi

  BUILDS=$(echo "$BUILDS" | jq -c --argjson entries "$entries" '. + $entries')
done

# Output JSON for GitHub Actions (compact, single line)
echo "$BUILDS" | jq -c .
