from pyspark.sql.functions import explode, substring, lit, col, avg, lag, collect_list,sort_array, size, struct, udf, split
from pyspark.sql.window import Window
from pyspark.sql.types import ArrayType, DoubleType
from pyspark.ml.feature import VectorAssembler
import operator



# df_pro_match_data = spark.read.json("/user/gl758/pro_matches_data/*.json")
df_pro_match_data = spark.read.json("/user/gl758/pro_matches_complete/*.json")

df_pro_match_players = df_pro_match_data.select('match_id', 'start_time', 'players')
df_player = df_pro_match_players.withColumn("players", explode(df_pro_match_players.players))

df_player = df_player.withColumn("kills", df_player.players.kills)
df_player = df_player.withColumn("assists", df_player.players.assists)
df_player = df_player.withColumn("deaths", df_player.players.deaths)
df_player = df_player.withColumn("gold_per_min", df_player.players.gold_per_min)

df_player = df_player.withColumn("account_id", df_player.players.account_id)
df_player = df_player.withColumn('radiant_win', df_player.players.radiant_win)
df_player = df_player.withColumn('is_radiant', df_player.players.isRadiant.cast("integer"))
df_player = df_player.drop('players')
df_player_features = df_player.dropna()

features = ['kills', 'deaths', 'assists', 'gold_per_min']
for feature in features:
    df_player_features = df_player_features.withColumn('{}_lag'.format(feature),lag(df_player_features[feature]).over(Window.partitionBy("account_id").orderBy("start_time")))
    wspec = Window.partitionBy("account_id").orderBy("start_time").rowsBetween(-9999999,0)
    df_player_features = df_player_features.withColumn("{}_avg".format(feature), avg(df_player_features['{}_lag'.format(feature)]).over(wspec))

df_player_features_dropped = df_player_features.dropna()

# df_player_features_dropped = spark.read.json('/user/gl758/esports_players_cleaned/esports_players/*.json')
features = ['kills_avg', 'deaths_avg', 'assists_avg', 'gold_per_min_avg', 'is_radiant']
# df_player_features_ordered = df_player_features.orderBy("match_id", "is_radiant")

df_player_features_ordered = df_player_features_dropped.withColumn("kills_order_col",struct(["is_radiant","kills_avg"]))
df_player_features_ordered = df_player_features_ordered.withColumn("deaths_order_col",struct(["is_radiant","deaths_avg"]))
df_player_features_ordered = df_player_features_ordered.withColumn("assists_order_col",struct(["is_radiant","assists_avg"]))
df_player_features_ordered = df_player_features_ordered.withColumn("gold_per_min_col",struct(["is_radiant","gold_per_min_avg"]))

df_match_id_radiant = df_player_features_ordered.select('match_id', 'radiant_win', 'start_time').distinct()
df_stat_in_one_row = df_player_features_ordered.groupby("match_id").agg(collect_list("kills_order_col").alias("kills_order_col"), collect_list("deaths_order_col").alias("deaths_order_col"), collect_list("assists_order_col").alias("assists_order_col"), collect_list("gold_per_min_col").alias("gold_per_min_col"))

df_players_features_with_win = df_stat_in_one_row.join(df_match_id_radiant, "match_id")

def sorter(l):
    res = sorted(l, key=operator.itemgetter(0))
    items= [item[1] for item in res]
    return items

sort_udf = udf(sorter, ArrayType(DoubleType()))

df_players_features_with_win_in_one_row = df_players_features_with_win.select("match_id", "radiant_win","start_time", sort_udf("kills_order_col").alias("kills_avg"), sort_udf("deaths_order_col").alias("deaths_avg"), sort_udf("assists_order_col").alias("assists_avg"), sort_udf("gold_per_min_col").alias("gold_per_min_avg"))

df_only_valid_player_stats = df_players_features_with_win_in_one_row.where(size(col("kills_avg")) == 10)
