#!/bin/bash

# Define colors
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check and copy with confirmation
check_and_copy() {
  source_file=$1
  target_file=$2

  if [ -f "$target_file" ]; then
    echo "Config ${YELLOW}$target_file${NC} already exists. Overwrite? (Y/N)" && read -n 1 -r
    echo "" # Newline for cleaner output
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      cp "$source_file" "$target_file"
      echo "${GREEN}Overwritten $target_file${NC}"
    else
      echo "${RED}Skipping $target_file${NC}"
    fi
  else
    cp "$source_file" "$target_file"
    echo "${GREEN}Copied $source_file to $target_file${NC}"
  fi
}

# Use the function for each file
check_and_copy .env.example .env
check_and_copy prompts/classify_prompt_example.txt prompts/classify_prompt.txt
check_and_copy prompts/default_prompt_example.txt prompts/default_prompt.txt
check_and_copy prompts/price_prompt_example.txt prompts/price_prompt.txt
check_and_copy prompts/tech_prompt_example.txt prompts/tech_prompt.txt
