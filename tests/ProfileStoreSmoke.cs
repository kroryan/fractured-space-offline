using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Web.Script.Serialization;
class ProfileTest {
 static int Main(string[] args) {
  var j=new JavaScriptSerializer {MaxJsonLength=int.MaxValue};
  var entries=(object[])j.DeserializeObject(File.ReadAllText("server/responses.json"));
  var a=new ProfileStore(args[0],"a");
  foreach(Dictionary<string,object> e in entries) {
   var req=(Dictionary<string,object>)e["request"]; var res=(Dictionary<string,object>)e["response"];
   string path=((string)req["url"]).Replace("https://api.fireteam.net/","").Split('?')[0];
   a.Register(path,Encoding.UTF8.GetBytes((string)res["content"]));
  }
  byte[] b; string stats="o/player_stats/bc7f731e-6af2-3f60-a2e0-5d938d5e3340";
  a.Handle("GET",stats,new byte[0],out b); var data=j.Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(b));
  if(Convert.ToInt32(data["kills"])!=0 || Convert.ToInt32(data["gamesPlayed"])!=0) throw new Exception("Inherited stats");
  a.Handle("PUT",stats,Encoding.UTF8.GetBytes("{\"kills\":3,\"gamesPlayed\":1}"),out b);
  var reload=new ProfileStore(args[0],"a"); reload.Register(stats,b); reload.Handle("GET",stats,new byte[0],out b);
  if(!Encoding.UTF8.GetString(b).Contains("\"kills\":3")) throw new Exception("Not persisted");
  var other=new ProfileStore(args[0],"b"); other.Register(stats,b); other.Handle("GET",stats,new byte[0],out b);
  if(!Encoding.UTF8.GetString(b).Contains("\"kills\":0")) throw new Exception("Identity leak");
  a.Action("reset_stats"); a.Handle("GET",stats,new byte[0],out b);
  if(!Encoding.UTF8.GetString(b).Contains("\"kills\":0")) throw new Exception("Reset failed");
  string report="{\"info\":{\"MatchId\":\"match-1\"},\"result\":{\"MatchResult\":0,\"StatsAmount\":[{\"StatName\":\"Deaths\",\"Amount\":2}]}}";
  a.RecordMatch(report); a.RecordMatch(report); a.Handle("GET",stats,new byte[0],out b);
  data=j.Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(b));
  if(Convert.ToInt32(data["gamesPlayed"])!=1 || Convert.ToInt32(data["gameWins"])!=1 || Convert.ToInt32(data["deaths"])!=2) throw new Exception("Match aggregation/deduplication failed");
  Console.WriteLine("Match aggregation and duplicate protection passed.");
  Console.WriteLine("Fresh statistics, persistence, identity isolation and reset passed."); return 0;
 }
}
