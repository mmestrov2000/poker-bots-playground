package main

import (
	"encoding/json"
	"fmt"
	"os"
)

type LegalAction struct {
	Action string `json:"action"`
}

type State struct {
	LegalActions []LegalAction `json:"legal_actions"`
}

type Response struct {
	Action string `json:"action"`
}

func main() {
	var state State
	if err := json.NewDecoder(os.Stdin).Decode(&state); err != nil {
		os.Exit(1)
	}

	response := Response{Action: "fold"}
	for _, entry := range state.LegalActions {
		if entry.Action == "check" {
			response.Action = "check"
			break
		}
		if entry.Action == "call" {
			response.Action = "call"
		}
	}

	if err := json.NewEncoder(os.Stdout).Encode(response); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
