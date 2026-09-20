package main
import("context";"encoding/json";"os";"time";"github.com/gastownhall/gascity/internal/convergence")
func main(){if len(os.Args)!=3{panic("script and city required")};r:=convergence.RunCondition(context.Background(),os.Args[1],convergence.ConditionEnv{CityPath:os.Args[2]},30*time.Second,0);json.NewEncoder(os.Stdout).Encode(r)}
