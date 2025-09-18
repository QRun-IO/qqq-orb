#!/bin/bash

############################################################################
## calculate_version.sh
## Intelligent version calculation for GitFlow branching strategy
## 
## This script determines the appropriate version based on:
## - Current branch name
## - Current version in pom.xml
## - GitFlow conventions
##
## Usage: ./calculate_version.sh [--dry-run]
## Output: Sets version in pom.xml and prints the new version
############################################################################

set -e

###################
## Configuration ##
###################
POM_FILE="${POM_FILE:-pom.xml}"
DRY_RUN=false

##################################
## Parse command line arguments ##
##################################
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "DRY RUN MODE - No changes will be made"
fi

####################################
## Get current branch and version ##
####################################
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_VERSION=$(grep '<revision>' "$POM_FILE" | sed 's/.*<revision>//;s/<.*//')

# Check if we're on a tag (HEAD means we're on a tag)
CURRENT_TAG=""
if [[ "$CURRENT_BRANCH" == "HEAD" ]]; then
    # Get the tag name we're on
    CURRENT_TAG=$(git describe --tags --exact-match HEAD 2>/dev/null || echo "")
    if [[ -n "$CURRENT_TAG" ]]; then
        echo "Currently on tag: $CURRENT_TAG"
        # Determine the branch type based on tag format
        if [[ "$CURRENT_TAG" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
            echo "This is a production release tag, treating as main branch"
            CURRENT_BRANCH="main"
        elif [[ "$CURRENT_TAG" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)-RC\.[0-9]+$ ]]; then
            echo "This is a release candidate tag, treating as release branch"
            CURRENT_BRANCH="release/${CURRENT_TAG#v}"
            CURRENT_BRANCH="release/${CURRENT_BRANCH%-RC.*}"
        else
            echo "Unknown tag format: $CURRENT_TAG"
            CURRENT_BRANCH="unknown"
        fi
    else
        echo "On HEAD but not on a tag, treating as main branch"
        CURRENT_BRANCH="main"
    fi
fi

echo "Current branch: $CURRENT_BRANCH"
echo "Current version: $CURRENT_VERSION"

############################################
## Function to extract version components ##
############################################
extract_version_parts() {
    local version=$1
    
    # Remove 'v' prefix if present
    if [[ "$version" =~ ^v(.+)$ ]]; then
        version=${BASH_REMATCH[1]}
    fi
    
    ########################################
    ## Handle RC versions like 1.5.0-RC.1 ##
    ########################################
    if [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)-RC\.[0-9]+$ ]]; then
        MAJOR=${BASH_REMATCH[1]}
        MINOR=${BASH_REMATCH[2]}
        PATCH=${BASH_REMATCH[3]}
    ##################################################
    ## Handle SNAPSHOT versions like 1.5.0-SNAPSHOT ##
    ##################################################
    elif [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)-SNAPSHOT$ ]]; then
        MAJOR=${BASH_REMATCH[1]}
        MINOR=${BASH_REMATCH[2]}
        PATCH=${BASH_REMATCH[3]}
    #######################################
    ## Handle stable versions like 1.5.0 ##
    #######################################
    elif [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        MAJOR=${BASH_REMATCH[1]}
        MINOR=${BASH_REMATCH[2]}
        PATCH=${BASH_REMATCH[3]}
    else
        echo "ERROR: Cannot parse version format: $version"
        exit 1
    fi
}

#########################################
## Function to set version using Maven ##
#########################################
set_version() {
    local new_version=$1
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "DRY RUN: Would set version to: $new_version"
        echo "Command: mvn versions:set-property -Dproperty=revision -DnewVersion=$new_version -DgenerateBackupPoms=false"
        return
    fi
    
    echo "Setting version to: $new_version"
    
    ##############################################
    ## Use Maven versions plugin to set version ##
    ##############################################
    mvn versions:set-property -Dproperty=revision -DnewVersion="$new_version" -DgenerateBackupPoms=false
    
    #######################
    ## Verify the change ##
    #######################
    ACTUAL_VERSION=$(grep "<revision>" "$POM_FILE" | sed 's/.*<revision>//;s/<.*//')
    if [[ "$ACTUAL_VERSION" == "$new_version" ]]; then
        echo "✅ Version successfully updated to: $ACTUAL_VERSION"
    else
        echo "❌ Version update failed. Expected: $new_version, Got: $ACTUAL_VERSION"
        exit 1
    fi
}

#############################################
## Branch Detection and Routing Functions ##
#############################################

detect_branch_type() {
    local branch=$1
    
    if [[ "$branch" == "main" ]]; then
        echo "main"
    elif [[ "$branch" == "develop" ]]; then
        echo "develop"
    elif [[ "$branch" =~ ^release/ ]]; then
        echo "release"
    elif [[ "$branch" =~ ^hotfix/ ]]; then
        echo "hotfix"
    elif [[ "$branch" =~ ^feature/ ]]; then
        echo "feature"
    else
        echo "unknown"
    fi
}

#############################################
## Branch-Specific Version Handlers       ##
#############################################

handle_main_branch() {
    echo "=== Handling MAIN branch ==="
    echo "Main branch should always have stable versions"
    echo "Looking for the most recent version tag"
    
    # If we're on a tag, use that tag; otherwise find the latest tag
    local latest_tag=""
    if [[ -n "$CURRENT_TAG" ]]; then
        latest_tag="$CURRENT_TAG"
        echo "Using current tag: $latest_tag"
    else
        latest_tag=$(git describe --tags --abbrev=0 --match="v*" 2>/dev/null || echo "")
        echo "Found latest tag: $latest_tag"
    fi
    
    if [[ -n "$latest_tag" ]]; then
        # Extract version from tag (e.g., v1.5.0 -> 1.5.0)
        if [[ "$latest_tag" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
            local tag_version=${BASH_REMATCH[1]}
            echo "Release tag: $latest_tag (version: $tag_version)"
            
            # Check if current version matches the tag
            if [[ "$CURRENT_VERSION" == "$tag_version" ]]; then
                echo "Version matches release tag, keeping stable version"
                NEW_VERSION="$CURRENT_VERSION"
            elif [[ "$CURRENT_VERSION" =~ -RC\.[0-9]+$ ]]; then
                echo "Converting RC version to tag version: $tag_version"
                NEW_VERSION="$tag_version"
            else
                NEW_VERSION="$tag_version"
            fi
        else
            echo "Warning: Tag format not recognized: $latest_tag"
            NEW_VERSION="$CURRENT_VERSION"
        fi
    else
        echo "ERROR: No version tags found on main branch"
        echo "Main branch should always have a corresponding release tag (e.g., v1.5.0)"
        echo "Please create a release tag before deploying from main"
        exit 1
    fi
}

handle_develop_branch() {
    echo "=== Handling DEVELOP branch ==="
    echo "Develop branch manages SNAPSHOT versions"
    
    # Check if we just merged a release branch back to develop
    local recent_release_merges=$(git log --oneline -10 --grep="Merge.*release.*into.*develop" --grep="Merge.*release.*back.*develop" --grep="Bump.*version.*after.*release.*v" --since="3 days ago" || true)
    
    # Also check if current version suggests we're ready for next cycle
    if [[ -n "$recent_release_merges" ]] || [[ "$CURRENT_VERSION" =~ -RC\.[0-9]+$ ]] || [[ "$CURRENT_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Recent release activity detected or RC/stable version found"
        echo "Bumping to next minor version SNAPSHOT"
        NEW_VERSION="$MAJOR.$((MINOR + 1)).0-SNAPSHOT"
    else
        echo "No recent release activity, keeping current SNAPSHOT version"
        NEW_VERSION="$CURRENT_VERSION"
    fi
}

handle_release_branch() {
    echo "=== Handling RELEASE branch ==="
    echo "Release branch manages RC versions"
    
    # Extract major.minor from branch name (e.g., release/1.5 -> 1.5.0-RC.n)
    if [[ "$CURRENT_BRANCH" =~ release/([0-9]+)\.([0-9]+) ]]; then
        local branch_major=${BASH_REMATCH[1]}
        local branch_minor=${BASH_REMATCH[2]}
        
        echo "Release branch: $branch_major.$branch_minor"
        
        # Check if we already have an RC version
        if [[ "$CURRENT_VERSION" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)-RC\.([0-9]+)$ ]]; then
            # Extract current RC number and increment it
            local current_rc=${BASH_REMATCH[4]}
            local new_rc=$((current_rc + 1))
            echo "Incrementing RC from $current_rc to $new_rc"
            NEW_VERSION="$branch_major.$branch_minor.0-RC.$new_rc"
        else
            # First RC for this release
            echo "Creating first RC for this release"
            NEW_VERSION="$branch_major.$branch_minor.0-RC.1"
        fi
    else
        echo "ERROR: Invalid release branch format: $CURRENT_BRANCH"
        echo "Expected format: release/X.Y (e.g., release/1.5)"
        exit 1
    fi
}

handle_hotfix_branch() {
    echo "=== Handling HOTFIX branch ==="
    echo "Hotfix branch bumps patch version"
    
    NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
    echo "Bumping patch version: $CURRENT_VERSION -> $NEW_VERSION"
}

handle_feature_branch() {
    echo "=== Handling FEATURE branch ==="
    echo "Feature branches inherit version from develop, no changes"
    
    NEW_VERSION="$CURRENT_VERSION"
    echo "Keeping current version: $NEW_VERSION"
}

handle_unknown_branch() {
    echo "=== Handling UNKNOWN branch ==="
    echo "Unknown branch type, keeping current version"
    
    NEW_VERSION="$CURRENT_VERSION"
    echo "Keeping current version: $NEW_VERSION"
}

####################
## Main execution ##
####################
main() {
    echo "=== QQQ Version Calculator ==="
    echo "Branch: $CURRENT_BRANCH"
    echo "Current version: $CURRENT_VERSION"
    echo ""
    
    ################################
    ## Extract version components ##
    ################################
    extract_version_parts "$CURRENT_VERSION"
    echo "Version components: MAJOR=$MAJOR, MINOR=$MINOR, PATCH=$PATCH"
    echo ""
    
    ############################
    ## Detect branch type and route ##
    ############################
    local branch_type=$(detect_branch_type "$CURRENT_BRANCH")
    echo "Detected branch type: $branch_type"
    echo ""
    
    ############################
    ## Route to appropriate handler ##
    ############################
    case "$branch_type" in
        "main")
            handle_main_branch
            ;;
        "develop")
            handle_develop_branch
            ;;
        "release")
            handle_release_branch
            ;;
        "hotfix")
            handle_hotfix_branch
            ;;
        "feature")
            handle_feature_branch
            ;;
        *)
            handle_unknown_branch
            ;;
    esac
    
    echo ""
    echo "Calculated next version: $NEW_VERSION"
    echo ""
    
    #######################################
    ## Set the version if it's different ##
    #######################################
    if [[ "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
        echo "Version change detected: $CURRENT_VERSION → $NEW_VERSION"
        set_version "$NEW_VERSION"
        
        ###################
        ## Show git diff ##
        ###################
        echo ""
        echo "Changes made:"
        git diff "$POM_FILE"
    else
        echo "No version change needed. Current version is correct for branch: $CURRENT_BRANCH"
    fi
    
    echo ""
    echo "=== Version calculation complete ==="
}

#######################
## Run main function ##
#######################
main "$@"